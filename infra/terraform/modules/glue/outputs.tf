output "database_name" {
  description = "Glue database name."
  value       = aws_glue_catalog_database.lakehouse.name
}

output "security_configuration_name" {
  description = "Glue security configuration name."
  value       = aws_glue_security_configuration.pipeline.name
}
