# Subscription Plans Setup Guide

This guide explains how to initialize subscription plans in different environments.

## Overview

Subscription plans are now stored in Firestore in the `subscription-plans` collection. Each environment (development, staging, production) needs to have its plans initialized separately.

## Initialization Script

The initialization script is located at: `api/scripts/init_subscription_plans.py`

## Setup Instructions

### Development Environment

```bash
cd api
./scripts/set_environment.sh development
python scripts/init_subscription_plans.py
```

### Staging Environment

```bash
cd api
./scripts/set_environment.sh staging
python scripts/init_subscription_plans.py
```

### Production Environment

```bash
cd api
./scripts/set_environment.sh production
python scripts/init_subscription_plans.py
```

## Default Plans

The script creates four subscription plans:

1. **Free Plan** (Default)
   - Price: $0/month
   - Users: 1
   - Reports: 10/month
   - Features: Basic Reports, 1 User, Email Support

2. **Starter Plan**
   - Price: $49/month
   - Users: 5
   - Reports: 50/month
   - Features: Advanced Reports, Up to 5 Users, Priority Email Support, API Access

3. **Professional Plan**
   - Price: $149/month
   - Users: 20
   - Reports: 200/month
   - Features: Premium Reports, Up to 20 Users, 24/7 Phone Support, Advanced API Access, Custom Integrations, Data Export

4. **Enterprise Plan**
   - Price: $499/month
   - Users: 100
   - Reports: 1000/month
   - Features: Enterprise Reports, Unlimited Users, Dedicated Account Manager, Custom SLA, Advanced Security, White-label Options, Priority Development

## Modifying Plans

To modify existing plans or add new ones:

1. Use the API endpoints:
   - `POST /api/v1/subscription-plans` - Create new plan
   - `PUT /api/v1/subscription-plans/{plan_id}` - Update existing plan

2. Or modify the `init_subscription_plans.py` script and re-run it (it will skip existing plans)

## Important Notes

- The script is idempotent - it can be run multiple times safely
- Only one plan can be marked as `is_default: true`
- Plans can be deactivated by setting `is_active: false`
- Each environment maintains its own set of plans
- Changes to plans affect new organizations only; existing organizations keep their current plans