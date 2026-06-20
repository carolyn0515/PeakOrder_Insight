output "vpc_id" {
  description = "Project VPC ID."
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs."
  value       = values(aws_subnet.private)[*].id
}

output "logs_endpoint_id" {
  description = "CloudWatch Logs interface VPC endpoint ID."
  value       = aws_vpc_endpoint.logs.id
}
