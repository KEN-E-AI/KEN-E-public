# Backend Transaction Patterns for KEN-E

This document outlines recommended transaction patterns for the KEN-E backend to ensure data consistency and handle partial write failures.

## Overview

The KEN-E backend uses Neo4j as the primary graph database and Firestore for metadata storage. This distributed system requires careful transaction handling to prevent data inconsistencies.

## Current Architecture

```
API Request → FastAPI → Neo4j (Account Creation) → Firestore (Metadata) → GCS (Bucket Creation)
```

### Challenges

- Neo4j and Firestore operate as separate systems
- No distributed transaction coordinator
- Partial failures can leave system in inconsistent state
- File uploads and bucket creation are non-critical but can fail

## Recommended Transaction Patterns

### 1. Saga Pattern (Recommended for Account Creation)

Implement compensating actions for each step:

```python
class AccountCreationSaga:
    def __init__(self, neo4j: Neo4jService, firestore: FirestoreService):
        self.neo4j = neo4j
        self.firestore = firestore
        self.completed_steps = []

    async def execute(self, account_data: AccountRequest) -> Account:
        try:
            # Step 1: Create account in Neo4j (atomic)
            account = await self._create_neo4j_account(account_data)
            self.completed_steps.append("neo4j_account")

            # Step 2: Create relationships in Neo4j (atomic)
            await self._create_neo4j_relationships(account.account_id, account_data.organization_id)
            self.completed_steps.append("neo4j_relationships")

            # Step 3: Create Firestore metadata (atomic)
            await self._create_firestore_metadata(account.account_id, account_data)
            self.completed_steps.append("firestore_metadata")

            # Step 4: Non-critical operations (isolated failures)
            await self._create_gcs_bucket(account.account_id)  # Failures logged but don't rollback

            return account

        except Exception as e:
            await self._compensate()
            raise

    async def _compensate(self):
        """Rollback completed steps in reverse order"""
        for step in reversed(self.completed_steps):
            try:
                if step == "firestore_metadata":
                    await self.firestore.delete_account_metadata(account_id)
                elif step == "neo4j_relationships":
                    await self.neo4j.execute_write_query(
                        "MATCH (a:Account {account_id: $id})-[r]-() DELETE r",
                        {"id": account_id}
                    )
                elif step == "neo4j_account":
                    await self.neo4j.execute_write_query(
                        "MATCH (a:Account {account_id: $id}) DELETE a",
                        {"id": account_id}
                    )
            except Exception as cleanup_error:
                logger.error(f"Compensation failed for {step}: {cleanup_error}")
```

### 2. Two-Phase Commit Pattern

For critical operations requiring strong consistency:

```python
class TwoPhaseCommitManager:
    async def create_account_2pc(self, account_data: AccountRequest) -> Account:
        transaction_id = generate_uuid()

        # Phase 1: Prepare
        neo4j_prepared = await self._prepare_neo4j(transaction_id, account_data)
        firestore_prepared = await self._prepare_firestore(transaction_id, account_data)

        if not (neo4j_prepared and firestore_prepared):
            await self._abort_all(transaction_id)
            raise HTTPException(500, "Transaction preparation failed")

        # Phase 2: Commit
        try:
            neo4j_result = await self._commit_neo4j(transaction_id)
            firestore_result = await self._commit_firestore(transaction_id)

            return neo4j_result
        except Exception as e:
            await self._abort_all(transaction_id)
            raise
```

### 3. Idempotency Pattern

Ensure operations can be safely retried:

```python
class IdempotentAccountService:
    def __init__(self, cache: Redis):
        self.cache = cache

    async def create_account_idempotent(
        self,
        account_data: AccountRequest,
        idempotency_key: str
    ) -> Account:
        # Check if operation already completed
        cached_result = await self.cache.get(f"account_create:{idempotency_key}")
        if cached_result:
            return Account.parse_raw(cached_result)

        # Check if account already exists with same data
        existing = await self._find_matching_account(account_data)
        if existing:
            await self.cache.setex(
                f"account_create:{idempotency_key}",
                3600,
                existing.json()
            )
            return existing

        # Create new account
        account = await self._create_account(account_data)

        # Cache result for future requests
        await self.cache.setex(
            f"account_create:{idempotency_key}",
            3600,
            account.json()
        )

        return account
```

### 4. Circuit Breaker Pattern

Prevent cascading failures:

```python
class DatabaseCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, operation):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise HTTPException(503, "Service temporarily unavailable")

        try:
            result = await operation()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"

            raise e
```

## Implementation Strategy

### Phase 1: Foundation (Immediate)

1. Add transaction boundaries to Neo4j operations
2. Implement basic rollback for account creation
3. Add idempotency key support to API endpoints

### Phase 2: Saga Implementation (Next Sprint)

1. Create AccountCreationSaga class
2. Add compensation logic for all steps
3. Update API endpoints to use saga pattern

### Phase 3: Monitoring & Recovery (Following Sprint)

1. Add health checks for consistency
2. Create automated recovery processes
3. Implement circuit breakers for external services

## Error Handling Strategy

### 1. Transient Errors

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def robust_neo4j_operation(query, params):
    return await neo4j_service.execute_query(query, params)
```

### 2. Permanent Errors

```python
async def handle_permanent_error(error, context):
    logger.error(f"Permanent error in {context}: {error}")

    # Don't retry, but ensure cleanup
    await cleanup_partial_state(context)

    # Notify monitoring system
    await send_alert("account_creation_failed", context)

    raise HTTPException(500, "Account creation failed permanently")
```

### 3. Consistency Checks

```python
async def verify_account_consistency(account_id: str) -> bool:
    neo4j_account = await neo4j_service.get_account(account_id)
    firestore_metadata = await firestore_service.get_account_metadata(account_id)

    if not neo4j_account or not firestore_metadata:
        return False

    # Verify critical fields match
    return (
        neo4j_account.account_name == firestore_metadata.account_name and
        neo4j_account.organization_id == firestore_metadata.organization_id
    )
```

## Testing Strategy

### 1. Chaos Engineering

```python
@pytest.mark.integration
async def test_neo4j_failure_during_account_creation():
    with mock.patch('neo4j_service.execute_query') as mock_neo4j:
        mock_neo4j.side_effect = ConnectionError("Neo4j unavailable")

        with pytest.raises(HTTPException) as exc_info:
            await account_service.create_account(test_data)

        assert exc_info.value.status_code == 500
        # Verify no partial data was created
        assert await firestore_service.get_account_metadata(test_id) is None
```

### 2. Race Condition Testing

```python
@pytest.mark.asyncio
async def test_concurrent_account_creation_idempotency():
    idempotency_key = "test-key-123"

    # Start multiple concurrent requests
    tasks = [
        account_service.create_account_idempotent(test_data, idempotency_key)
        for _ in range(10)
    ]

    results = await asyncio.gather(*tasks)

    # All results should be identical
    assert all(r.account_id == results[0].account_id for r in results)
```

## Monitoring & Alerts

### Key Metrics

- Account creation success rate
- Average transaction completion time
- Rollback frequency
- Consistency check results

### Alert Conditions

- Success rate < 95%
- Rollback frequency > 1%
- Consistency checks failing
- Transaction time > 30 seconds

### Dashboards

- Real-time transaction status
- Error rate trends
- System health indicators
- Performance metrics

## Recovery Procedures

### Manual Recovery Steps

1. Identify affected accounts using consistency checks
2. Determine missing data from logs
3. Execute repair queries to restore consistency
4. Verify system health after recovery

### Automated Recovery

```python
async def automated_recovery_job():
    """Run daily to detect and fix consistency issues"""
    inconsistent_accounts = await find_inconsistent_accounts()

    for account_id in inconsistent_accounts:
        try:
            await repair_account_consistency(account_id)
            logger.info(f"Repaired account {account_id}")
        except Exception as e:
            logger.error(f"Failed to repair account {account_id}: {e}")
            await escalate_to_human(account_id, e)
```

This documentation should be used as a reference for implementing robust transaction handling in the KEN-E backend.
