DEMO_PASSWORD = "password123"
# Fixed salt is exclusively for reproducible public demo credentials, never new accounts.
DEMO_PASSWORD_SALT = b"$2b$12$LQv3c1yqBWVHxkd0LHAkCO"
DEMO_KEYS = (
    "incident-relay-demo-checkout-key-2026",
    "incident-relay-demo-payments-key-2026",
    "incident-relay-demo-identity-key-2026",
    "incident-relay-demo-notifications-key-2026",
)

USER_ROWS = [
    {"name": "Alex Morgan", "email": "alex.morgan@calendar.com", "avatarColor": "#4285f4"},
    {"name": "Jordan Smith", "email": "jordan.smith@calendar.com", "avatarColor": "#0f9d58"},
    {"name": "Taylor Johnson", "email": "taylor.johnson@calendar.com", "avatarColor": "#ab47bc"},
    {"name": "Riley Parker", "email": "riley.parker@calendar.com", "avatarColor": "#ef6c00"},
    {"name": "Casey Bennett", "email": "casey.bennett@calendar.com", "avatarColor": "#00838f"},
]

SERVICE_ROWS = [
    {
        "name": "Checkout API", "description": "Creates checkout sessions and confirms customer orders.",
        "defaultSeverity": "HIGH", "groupingWindowMinutes": 30,
        "workflowTemplate": [
            {"title": "Diagnose database latency", "instructions": "Compare query duration, connection pool saturation, and recent changes.", "order": 1, "required": True},
            {"title": "Mitigate and verify checkout", "instructions": "Apply the reviewed database mitigation, then verify successful checkout and normal latency.", "order": 2, "required": True},
        ],
    },
    {
        "name": "Payments Gateway", "description": "Authorizes and reconciles customer payments.",
        "defaultSeverity": "HIGH", "groupingWindowMinutes": 30,
        "workflowTemplate": [
            {"title": "Confirm authorization failures", "instructions": "Identify affected payment methods and compare error rates by region.", "order": 1, "required": True},
            {"title": "Restore payment processing", "instructions": "Apply the approved routing or configuration change and verify authorization success.", "order": 2, "required": True},
        ],
    },
    {
        "name": "Identity Service", "description": "Issues sessions and validates token refresh requests.",
        "defaultSeverity": "HIGH", "groupingWindowMinutes": 30,
        "workflowTemplate": [
            {"title": "Inspect authentication errors", "instructions": "Compare token validation failures against deployment and configuration changes.", "order": 1, "required": True},
            {"title": "Restore session reliability", "instructions": "Revert the faulty configuration or deployment and verify login and refresh flows.", "order": 2, "required": True},
        ],
    },
    {
        "name": "Notifications Service", "description": "Coordinates customer notification delivery.",
        "defaultSeverity": "MEDIUM", "groupingWindowMinutes": 30,
        "workflowTemplate": [
            {"title": "Identify delivery delays", "instructions": "Review failed delivery counts, processing latency, and capacity changes.", "order": 1, "required": True},
            {"title": "Verify delivery recovery", "instructions": "Apply the approved capacity adjustment and confirm processing latency has recovered.", "order": 2, "required": True},
        ],
    },
]

HISTORY = [
    {"service": 0, "severity": "MEDIUM", "title": "Checkout connection pool saturation", "description": "A deployment reduced available database connections.", "note": "Connection limits matched the deployment diff.", "resolution": "Restored the pool limit and verified successful checkout."},
    {"service": 1, "severity": "HIGH", "title": "Payment authorization timeouts", "description": "Authorization latency increased in the primary region.", "note": "The regional route was identified as the bottleneck.", "resolution": "Adjusted regional routing and verified authorizations."},
    {"service": 2, "severity": "CRITICAL", "title": "Login token validation failures", "description": "A token configuration change rejected valid sessions.", "note": "The previous validator configuration passed replay checks.", "resolution": "Restored token configuration and verified sign-in."},
    {"service": 3, "severity": "LOW", "title": "Notification processing delay", "description": "Delivery throughput fell below the expected baseline.", "note": "Processing capacity was below the reviewed target.", "resolution": "Restored capacity and cleared delivery delays."},
    {"service": 0, "severity": "CRITICAL", "title": "Checkout database latency", "description": "Slow database queries caused elevated checkout latency and errors.", "note": "The slow query was isolated; the reviewed mitigation restored checkout latency.", "resolution": "Applied the query mitigation, verified successful checkouts, and confirmed normal database latency."},
    {"service": 1, "severity": "MEDIUM", "title": "Payment reconciliation lag", "description": "Completed payments took longer to reconcile.", "note": "The reconciliation batch size exceeded the stable operating range.", "resolution": "Reduced batch size and verified reconciliation completion."},
    {"service": 2, "severity": "HIGH", "title": "Refresh token error increase", "description": "Refresh requests failed after a configuration release.", "note": "Errors correlated with the new refresh validator.", "resolution": "Rolled back the validator and verified token refresh."},
    {"service": 1, "severity": "MEDIUM", "title": "Regional payment failures", "description": "Payment failures spread from one region to both regions.", "note": "The payment owner coordinated mitigation after manual escalation.", "resolution": "Restored the shared routing configuration and verified both regions."},
    {"service": 0, "severity": "HIGH", "title": "Checkout cache timeout", "description": "Checkout requests waited on an unhealthy cache connection.", "note": "Cache connection timeout settings caused request accumulation.", "resolution": "Corrected timeout settings and verified checkout response times."},
    {"service": 3, "severity": "MEDIUM", "title": "Notification retry backlog", "description": "Retries accumulated after a capacity adjustment.", "note": "The prior capacity configuration restored steady processing.", "resolution": "Restored processing capacity and verified the backlog cleared."},
    {"service": 2, "severity": "LOW", "title": "Session lookup latency", "description": "Session lookup latency increased without total sign-in failure.", "note": "A changed lookup path caused unnecessary database reads.", "resolution": "Restored the indexed lookup path and verified latency."},
    {"service": 0, "severity": "HIGH", "title": "Checkout query regression", "description": "A new query plan increased order confirmation latency.", "note": "The previous plan remained stable under the same workload.", "resolution": "Restored the query plan and verified order confirmation."},
    {"service": 1, "severity": "CRITICAL", "title": "Payment routing configuration error", "description": "An incorrect route caused widespread authorization failures.", "note": "The invalid route was isolated during configuration review.", "resolution": "Restored the approved routing map and verified payments."},
    {"service": 3, "severity": "MEDIUM", "title": "Notification delivery latency", "description": "Delivery latency increased after a deployment.", "note": "The deployment changed processing limits.", "resolution": "Reverted the processing limit change and verified delivery latency."},
    {"service": 2, "severity": "HIGH", "title": "Identity validation timeout", "description": "A validation dependency caused intermittent session timeouts.", "note": "The timeout configuration exceeded the request budget.", "resolution": "Corrected the timeout and verified session reliability."},
]
