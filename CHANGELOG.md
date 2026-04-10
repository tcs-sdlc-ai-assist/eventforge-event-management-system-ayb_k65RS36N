# Changelog

All notable changes to the EventForge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added

#### User Management
- User registration with email validation and secure password hashing
- User login with JWT-based authentication and token refresh
- User profile viewing and editing
- Role-based access control for organizers and attendees

#### Event Management
- Full CRUD operations for events (create, read, update, delete)
- Event listing with pagination and filtering support
- Event detail pages with comprehensive event information
- Support for event start/end dates, location, and capacity limits
- Event status management (draft, published, cancelled, completed)

#### Ticketing
- Ticket type creation and management per event
- Ticket purchasing with quantity validation against available inventory
- Ticket price configuration with support for free and paid events
- Ticket inventory tracking with real-time availability updates

#### RSVP System
- RSVP creation and management for events
- RSVP status tracking (pending, confirmed, declined)
- Attendee list management for event organizers

#### Check-In
- Attendee check-in functionality for event day operations
- Check-in status tracking and validation against ticket records
- Duplicate check-in prevention

#### Search
- Event search by title, description, and location
- Filtering by date range, category, and event status
- Paginated search results with sorting options

#### Dashboards
- Organizer dashboard with event statistics and attendee metrics
- Attendee dashboard with upcoming events and ticket history
- Summary statistics including total events, tickets sold, and revenue

#### Category Management
- Event category creation and management
- Category-based event organization and filtering
- Support for multiple categories per event

#### Seed Data
- Database seeding script for development and testing
- Sample users, events, categories, and tickets for quick setup
- Reproducible seed data for consistent development environments

#### Infrastructure
- FastAPI application with async request handling
- SQLAlchemy 2.0 async ORM with SQLite/PostgreSQL support
- Pydantic v2 schemas for request/response validation
- JWT authentication with secure token generation
- CORS middleware configuration
- Structured logging throughout the application
- Comprehensive error handling with appropriate HTTP status codes