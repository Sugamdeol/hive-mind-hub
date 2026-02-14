# Hive Mind Hub

Distributed agent orchestration hub for controlling multiple nanobots.

## Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Sugamdeol/hive-mind-hub)

## Features

- Agent registration with unique passwords
- Task assignment and tracking
- Project auto-division
- Broadcast messaging
- Real-time dashboard

## API Endpoints

- `POST /register` - Register new agent
- `POST /token` - Get JWT token
- `GET /api/agents` - List agents
- `GET /api/tasks` - List tasks
- `POST /api/tasks` - Create task
- `POST /api/broadcast` - Broadcast message
- `GET /api/projects` - List projects

## Dashboard

Access the control panel at `/dashboard/index.html`
