# Contributing to Construction Taxonomy

Thank you for your interest in contributing to our construction taxonomy repository! This document provides guidelines for submitting changes and working with our data formats.

## JSON Format and Validation

All taxonomy data is stored in JSON format according to the schemas in the `/schema` directory:

- **Attributes**: Follow `attribute.schema.json` schema with required fields: name, type, and category
- **Categories**: Follow `category.schema.json` schema with proper hierarchy structure
- **Products**: Follow `product.schema.json` schema with the required attributes

Always validate your changes before submitting by running:

```bash
python scripts/validate.py
```

## The 80% Rule for Attributes

When assigning attributes to a category, consider the "commonality threshold" value. This represents the expected percentage of products in that category that should have this attribute. For example:

- A threshold of 100 means every product in this category must have this attribute
- A threshold of 80 means at least 80% of products typically have this attribute

This helps maintain consistent taxonomies across the system while allowing for flexibility where needed.

## Pull Request Workflow

1. Fork the repository (if external) or create a branch (if internal)
2. Make your changes following the JSON schemas
3. Validate your changes using the validation script
4. Submit a PR with a clear description of changes
5. Indicate whether changes were human-authored or AI-assisted
6. Address any review comments
7. Once approved, changes will be merged

## AI-Assisted Contributions

We welcome AI-assisted contributions! Please indicate in your PR if you used AI tools to help generate or refine the taxonomy data. This is not to discourage such contributions but to help us understand the source of the changes.
