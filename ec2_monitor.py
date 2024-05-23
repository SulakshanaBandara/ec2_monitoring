
import json
import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import schedule
import time

# Load configuration from JSON file
try:
    with open('configurations/config.json') as f:
        config = json.load(f)
except Exception as e:
    error_msg = f"Error loading configuration: {e}"
    print(error_msg)
    logging.error(error_msg)
    exit(1)

# Initialize boto3 clients for CloudWatch, SNS, and EC2
cloudwatch = boto3.client('cloudwatch', region_name=config['region'])
sns = boto3.client('sns', region_name=config['region'])
ec2 = boto3.resource('ec2', region_name=config['region'])

# Set up logging configuration
logging.basicConfig(filename=config['log_file'], level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Function to notify stakeholders via SNS
def notify_stakeholders(error_message):
    try:
        sns.publish(
            TopicArn=config['error_topic_arn'],
            Subject='Error Notification: EC2 Monitoring',
            Message=error_message
        )
        logging.info("Error notification sent to stakeholders")
    except ClientError as e:
        logging.error(f"Error sending error notification: {e}")

# Function to create an SNS topic
def create_sns_topic():
    try:
        response = sns.create_topic(Name=config['sns_topic_name'])
        logging.debug(f"SNS topic created: {response['TopicArn']}")
        return response['TopicArn']
    except ClientError as e:
        error_msg = f"Error creating SNS topic: {e}"
        logging.error(error_msg)
        notify_stakeholders(error_msg)
        raise

# Function to subscribe an email to an SNS topic
def subscribe_email(topic_arn, email):
    try:
        sns.subscribe(TopicArn=topic_arn, Protocol='email', Endpoint=email)
        logging.debug(f"Subscribed {email} to SNS topic {topic_arn}")
    except ClientError as e:
        error_msg = f"Error subscribing email to SNS topic: {e}"
        logging.error(error_msg)
        notify_stakeholders(error_msg)
        raise

# Function to create CloudWatch alarms for each instance and each stat
def create_alarms(topic_arn):
    for instance_id in config['instances']:
        for stat in config['stats']:
            sns_action = [topic_arn]
            try:
                cloudwatch.put_metric_alarm(
                    AlarmName=f'{instance_id}_{stat}_Amber_Alarm',
                    MetricName=stat,
                    Namespace='AWS/EC2',
                    Statistic='Average',
                    Period=60,
                    EvaluationPeriods=1,
                    Threshold=config['thresholds'][stat]['amber'],
                    ComparisonOperator='GreaterThanThreshold',
                    AlarmActions=sns_action,
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
                )
                cloudwatch.put_metric_alarm(
                    AlarmName=f'{instance_id}_{stat}_Red_Alarm',
                    MetricName=stat,
                    Namespace='AWS/EC2',
                    Statistic='Average',
                    Period=60,
                    EvaluationPeriods=1,
                    Threshold=config['thresholds'][stat]['red'],
                    ComparisonOperator='GreaterThanThreshold',
                    AlarmActions=sns_action,
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
                )
                logging.debug(f"Created alarms for {stat} on {instance_id}")
            except ClientError as e:
                error_msg = f"Error creating CloudWatch alarm for {stat} on {instance_id}: {e}"
                logging.error(error_msg)
                notify_stakeholders(error_msg)
                raise

# Function to record metrics to a JSON file
def record_metrics():
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=5)
    metrics_data = {"timestamp": str(end_time), "metrics": []}

    for instance_id in config['instances']:
        instance_metrics = {"instance_id": instance_id, "stats": {}}
        for stat in config['stats']:
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName=stat,
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=60,
                    Statistics=['Average']
                )
                logging.debug(f"Response for {stat} on {instance_id}: {response}")
                data_points = response['Datapoints']
                if data_points:
                    average_value = data_points[0]['Average']
                    instance_metrics['stats'][stat] = average_value
                else:
                    instance_metrics['stats'][stat] = None  # No data points available
            except ClientError as e:
                logging.error(f"Error getting metric statistics for {stat} on {instance_id}: {e}")
                instance_metrics['stats'][stat] = None
                notify_stakeholders(f"Error getting metric statistics for {stat} on {instance_id}: {e}")
                continue
        metrics_data['metrics'].append(instance_metrics)

    logging.debug(f"Metrics data recorded: {metrics_data}")

    try:
        with open(config['metrics'], 'a') as f:  # Changed to config['metrics']
            json.dump(metrics_data, f)
            f.write('\n')
    except IOError as e:
        logging.error(f"Error writing metrics data to file: {e}")
        notify_stakeholders(f"Error writing metrics data to file: {e}")
        raise

# Function to send a weekly summary email
def send_weekly_summary(topic_arn):
    try:
        with open(config['data_file']) as f:
            data = [json.loads(line) for line in f]

        weekly_summary = {}
        for stat in config['stats']:
            values = [entry['metrics'][0]['stats'][stat] for entry in data if entry['metrics'][0]['stats'][stat] is not None]
            if values:
                weekly_summary[stat] = {
                    'high': max(values),
                    'low': min(values),
                    'average': sum(values) / len(values)
                }

        summary_message = "Weekly Summary:\n"
        for stat, summary in weekly_summary.items():
            summary_message += f"\n{stat}:\n  High: {summary['high']}\n  Low: {summary['low']}\n  Average: {summary['average']}"

        sns.publish(
            TopicArn=topic_arn,
            Subject='Weekly EC2 Metrics Summary',
            Message=summary_message
        )
        logging.debug(f"Weekly summary sent: {summary_message}")
    except ClientError as e:
        error_msg = f"Error sending weekly summary: {e}"
        logging.error(error_msg)
        notify_stakeholders(error_msg)
        raise


# Main function to set up monitoring and scheduling tasks
def main():
    try:
        topic_arn = create_sns_topic()
        subscribe_email(topic_arn, config['email'])
        create_alarms(topic_arn)
    except Exception as e:
        error_msg = f"Setup failed: {e}"
        logging.error(error_msg)
        notify_stakeholders(error_msg)
        print(error_msg)
        return

    print("Setup complete, entering main loop.")

    # Schedule tasks
    schedule.every(1).minute.do(record_metrics)
    schedule.every().sunday.at("00:00").do(send_weekly_summary, topic_arn=topic_arn)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()