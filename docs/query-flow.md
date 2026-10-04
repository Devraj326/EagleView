# Query Flow

This diagram describes what happens after a signed-in user asks a question from the dashboard.

## Main Request Flow

```mermaid
flowchart TD
    A[User asks a question] --> B[Frontend POST /api/query]
    B --> C{Bearer token valid?}
    C -- No --> C1[401 Unauthorized]
    C -- Yes --> D[Load current user]
    D --> E[ready_context]
    E --> E1[Get shared Snowpark session]
    E1 --> E2[Create user schema if needed]
    E2 --> E3[Ensure metadata tables exist]
    E3 --> F[Start activity capture]
    F --> G[query_pipeline.ask_question]
    G --> H[Create or reuse session_id]
    H --> I[Save user question to APP_CONVERSATIONS]
    I --> J[List ready domains and table row counts]
    J --> K{Any uploaded data?}

    K -- No --> K1[Return no-data answer]
    K1 --> K2[Save assistant answer]
    K2 --> R[Return JSON response + agent_log]

    K -- Yes --> L[Build dataset catalog]
    L --> L1[Read relationships and live table columns]
    L1 --> M[Load recent conversation history]
    M --> N[Query Understanding Cortex call]
    N --> O{Intent}

    O -- clarification --> O1[Return one clarifying question]
    O1 --> O2[Save assistant answer]
    O2 --> R

    O -- analytics --> P[Select primary relevant domain agent]
    O -- entity investigation --> Q[Select all relevant domain agents]
    P --> S[Domain agent writes and runs query]
    Q --> T{More than one agent?}
    T -- Yes --> T1[Create independent Snowpark sessions]
    T1 --> T2[Run agents in parallel]
    T -- No --> S
    T2 --> U[Collect agent results]
    S --> U

    U --> V{SQL and rows accepted?}
    V -- No --> V1[Return data-not-available or no-record answer]
    V1 --> V2[Save assistant answer]
    V2 --> R
    V -- Yes --> W[Validate one read-only SELECT/WITH query]
    W --> X{Validation passed?}
    X -- No --> X1[Discard agent result]
    X1 --> V1
    X -- Yes --> Y[Result Interpretation Cortex call]
    Y --> Z[Build answer, result, summary, timeline, SQL]
    Z --> Z1[Save assistant answer and generated SQL]
    Z1 --> R
```

## Scenario 1: Analytics Question

Example: `What were total sales last month?`

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI /api/query
    participant QU as Query Understanding
    participant DA as Domain Agent
    participant SF as Snowflake
    participant RI as Result Interpretation

    U->>API: Ask analytics question
    API->>QU: Question + catalog + recent history
    QU-->>API: intent=analytics, relevant tables
    API->>DA: Question + catalog
    DA->>SF: Generate and run read-only SQL
    SF-->>DA: Rows + SQL used
    DA-->>API: SQL and rows
    API->>API: Validate SQL and table scope
    API->>RI: Question + understanding + rows
    RI-->>API: Plain-English answer and summary
    API-->>U: Answer, rows, SQL, summary, agent log
```

## Scenario 2: Entity Investigation

Example: `What happened with order 1234?`

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant QU as Query Understanding
    participant OA as Order Agent
    participant DA as Delivery Agent
    participant SF as Snowflake
    participant RI as Result Interpretation

    U->>API: Ask about one entity
    API->>QU: Question + catalog + history
    QU-->>API: intent=entity_investigation, entity=order/1234
    par Relevant domain agents
        API->>OA: Investigate order 1234
        OA->>SF: Run order query
        SF-->>OA: Order rows
    and
        API->>DA: Check delivery facts for order 1234
        DA->>SF: Run delivery query
        SF-->>DA: Delivery rows
    end
    OA-->>API: SQL and rows
    DA-->>API: SQL and rows
    API->>API: Validate each read-only query
    API->>RI: All accepted rows + entity context
    RI-->>API: Narrative, summary, timeline
    API-->>U: Entity answer and related results
```

## Scenario 3: Clarification

Example: `Show me the revenue.` when the data or time period is ambiguous.

```mermaid
flowchart LR
    A[Question] --> B[Query Understanding]
    B --> C{Ambiguous?}
    C -- Yes --> D[Create one short clarification question]
    D --> E[Save it in conversation history]
    E --> F[Return intent=clarification]
    C -- No --> G[Continue to a domain agent]
```

No SQL or Result Interpretation call is made for the clarification response.

## Scenario 4: No Data, No Match, or Invalid Result

```mermaid
flowchart TD
    A[Question] --> B{Ready domains exist?}
    B -- No --> C["Upload and confirm a file first"]
    B -- Yes --> D[Agent query]
    D --> E{Agent returned a usable query?}
    E -- No --> F[Information is not available]
    E -- Yes --> G{Rows found?}
    G -- No for entity --> H[No record found for requested ID]
    G -- No for analytics --> I[No records matched]
    G -- Yes --> J[Interpret results]
    D --> K{SQL is read-only and user-scoped?}
    K -- No --> L[Discard query and treat as unavailable]
    K -- Yes --> G
```

## What Is Returned

Every path returns the same basic response shape:

- `session_id`: conversation identifier
- `answer`: user-facing text
- `intent`: analytics, entity investigation, clarification, or error
- `result`: raw result rows
- `timeline`: entity events when available
- `summary`: key facts when available
- `sql`: accepted generated SQL when available
- `agents_consulted`: domain agents that returned accepted results
- `agent_log`: captured progress messages
- `missing_info`: expected facts absent from the uploaded data
