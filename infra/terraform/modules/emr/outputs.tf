output "application_id" {
  description = "EMR Serverless Spark application ID."
  value       = aws_emrserverless_application.spark.id
}

output "application_arn" {
  description = "EMR Serverless Spark application ARN."
  value       = aws_emrserverless_application.spark.arn
}

output "security_group_id" {
  description = "Security group used by EMR Serverless jobs."
  value       = aws_security_group.emr_serverless.id
}
