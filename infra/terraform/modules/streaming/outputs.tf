output "order_events_stream_name" {
  description = "Kinesis order events stream name."
  value       = aws_kinesis_stream.orders.name
}

output "order_events_stream_arn" {
  description = "Kinesis order events stream ARN."
  value       = aws_kinesis_stream.orders.arn
}
