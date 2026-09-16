<h1 align="center">Calendar</h1>

<p align="center">
  A HackerRank sample repo for personal scheduling and team coordination.
</p>

<img src="./assets/calendar-scheduling.jpg" alt="Calendar Event editor opened from the Create menu" width="100%">

## Built With

- [React 19](https://react.dev/) and [Vite 8](https://vite.dev/) for the frontend
- [Bun](https://bun.sh/) for JavaScript workspace installation
- [Python 3.12](https://www.python.org/), [Django 5.1](https://www.djangoproject.com/), and [Django REST Framework](https://www.django-rest-framework.org/) for the HTTP API
- [MongoDB](https://www.mongodb.com/) and [MongoEngine](https://mongoengine.org/) for persistence without the Django ORM
- Feature schemas and shared validation utilities for request validation
- [PyJWT](https://pyjwt.readthedocs.io/) and [bcrypt](https://pypi.org/project/bcrypt/) for authentication

## Project Structure

```text
.
├── backend/                     # Django API, business logic, and MongoDB persistence
│   ├── apps/                    # Product domains and API flows
│   ├── calendar_backend/        # Django settings and URL composition
│   ├── scripts/                 # Deterministic seed data
│   └── public/                  # Backend-served local media
├── frontend/
│   ├── src/features/            # Product views and interactions
│   ├── src/shared/              # API client, reusable controls, and utilities
│   └── public/                  # Local static media
├── .vscode/launch.json          # Django debugger configuration
├── hackerrank.yml               # HackerRank install and run configuration
└── setup.sh                     # Python, MongoDB, and seed setup
```

## Getting Started

### Prerequisites

- Bun 1.3 or later
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- MongoDB 8.0 or later on `127.0.0.1:27017`

### Development Setup

1. Clone the repository.

   ```bash
   git clone https://github.com/ProblemSetters/coderepo-react-django-calendar.git
   ```

2. Open the project directory.

   ```bash
   cd coderepo-react-django-calendar
   ```

3. Install the pinned JavaScript workspace.

   ```bash
   bun install
   ```

4. Start the complete application.

   ```bash
   bun start
   ```

   Startup prepares the Python environment, checks MongoDB, restores the seeded baseline, and launches the frontend and backend.

5. Open [http://localhost:3000](http://localhost:3000) and sign in.

   ```text
   Email: alex.morgan@calendar.com
   Password: password123
   ```

   Choose any seeded profile to enter the calendar workspace.

The frontend runs on port `3000`, the API runs on port `8000`, and health is available at [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health).

### Commands

| Command | Purpose |
|---|---|
| `bun start` | Seeds MongoDB and starts Django and Vite together. |
| `bun run seed` | Restores the deterministic MongoDB baseline. |
| `bun run dev:backend` | Starts only the Django API on port `8000`. |
| `bun run dev:frontend` | Starts only Vite on port `3000`. |

HackerRank installs the application with `bun install && bash setup.sh --seed` and runs it with `bun start`.
