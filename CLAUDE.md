# CLAUDE.md - AI Assistant Guide for Zuper-data

## Project Overview

**Zuper-data** is a data integration project for pulling and working with Zuper field service management data. This repository is in early development stage.

## Repository Structure

```
Zuper-data/
├── README.md          # Project description
├── CLAUDE.md          # This file - AI assistant guidelines
└── (future structure to be defined)
```

## Purpose

This project is designed to:
- Pull data from Zuper's field service management platform
- Process and transform Zuper data for downstream use
- Provide data integration capabilities with Zuper APIs

## Development Guidelines

### For AI Assistants

When working on this repository:

1. **Understand the Context**: This is a data integration project focused on Zuper. Research Zuper's API documentation when implementing data pulling functionality.

2. **Code Style**:
   - Follow language-specific best practices for whichever language is chosen
   - Write clear, documented code especially for API interactions
   - Handle API errors gracefully with proper logging

3. **Security Practices**:
   - Never commit API keys, secrets, or credentials
   - Use environment variables for sensitive configuration
   - Implement proper authentication handling for Zuper API

4. **Data Handling**:
   - Respect rate limits when pulling data from Zuper
   - Implement pagination for large data sets
   - Add appropriate data validation and sanitization

### Branch Conventions

- Feature branches should use descriptive names
- Claude AI-generated branches follow pattern: `claude/<description>-<session-id>`

### Commit Messages

- Use clear, descriptive commit messages
- Format: `<type>: <description>`
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Getting Started

As this project develops, add:
- Installation instructions
- Configuration steps (environment variables, API credentials)
- Usage examples

## Zuper Integration Notes

When implementing Zuper data pulling:

1. **Authentication**: Zuper APIs typically require API key authentication
2. **Endpoints**: Common data types include:
   - Jobs/Work Orders
   - Customers
   - Teams/Technicians
   - Assets
   - Invoices
3. **Rate Limiting**: Be mindful of API rate limits
4. **Webhooks**: Consider webhook support for real-time updates

## Testing

When tests are added:
- Run tests before committing changes
- Maintain good test coverage for data transformation logic
- Mock external API calls in unit tests

## Dependencies

Dependencies will be tracked in language-appropriate manifest files (e.g., `package.json`, `requirements.txt`, `Cargo.toml`) as the project develops.

---

*Last updated: December 2025*
