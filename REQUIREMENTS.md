# Requirements

## Overview

Build a PagerDuty-inspired incident management app that helps on-call teams receive events, manage incidents, and coordinate response. Think beyond an incident list and a status badge.

The app is full-stack React + Django (Python). It keeps the React frontend and Django backend of the sample calendar repo you clone, and it persists data in MongoDB. Every feature you ship must work end to end: a usable screen, a real API call, a backend handler, and stored data.

Pick five to ten features from the list below, or add your own of the same weight. Fewer than five is under scope. More than ten spreads the work too thin.

## Feature set

- **Service and event management.** Register services with an owner and integration key. Accept events from monitoring tools through that key and attach them to the right service.
- **Incident management.** Open an incident from an event or by hand. Acknowledge, assign, escalate, add notes, and resolve it, with each state change recorded.
- **On-call scheduling.** Build rotations with named users, shift lengths, and handoff times. Add a temporary override for a day or a week.
- **Escalation policies.** Define an ordered list of responders per service with a timeout for each level. Move an unacknowledged incident to the next level when the timeout passes.
- **Alert triage.** Group related alerts under one incident by service, time window, or title. Suppress duplicates so responders see one item instead of many.
- **Incident workflows.** Attach a checklist of response steps to a service. Run it on a new incident and track which steps are done.
- **Stakeholder communication.** Post status updates on an incident. Show a service status page that reflects open incidents.
- **Post-incident analytics.** List past incidents with time to acknowledge and time to resolve. Summarize trends per service and per responder.

## Acceptance criteria

- **Five to ten features**, each working end to end through the UI, the API, and MongoDB.
- **Human judgment is visible.** AI can write the code. Feature selection, architecture, and production readiness must be your own decisions, and the transcripts should show it.
- **Modern, polished UI.** Responsive, keyboard accessible, with loading, empty, validation, and error states where they apply.
- **Clean checkout works.** The app installs, builds, and starts without errors using the commands in `hackerrank.yml`.
- **Current stack.** Dependency versions are at least as recent as the sample calendar repo. Do not downgrade, and do not swap out the declared stack.
- **Matches the sample repo in scope, structure, and quality.** Use the calendar app as the bar for what "done" looks like.
