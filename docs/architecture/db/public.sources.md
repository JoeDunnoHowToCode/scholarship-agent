# public.sources

## Columns

| Name | Type | Default | Nullable | Children | Parents | Comment |
| ---- | ---- | ------- | -------- | -------- | ------- | ------- |
| agent_run_id | bigint |  | true |  | [public.agent_runs](public.agent_runs.md) |  |
| check_interval_hours | integer | 24 | false |  |  |  |
| country | text |  | true |  |  |  |
| created_at | timestamp with time zone | now() | false |  |  |  |
| decided_at | timestamp with time zone |  | true |  |  |  |
| disabled_at | timestamp with time zone |  | true |  |  |  |
| discovery | varchar(16) | 'seed'::character varying | false |  |  |  |
| empty_extractions | integer | 0 | false |  |  |  |
| enabled | boolean | true | false |  |  |  |
| fail_days | integer | 0 | false |  |  |  |
| fetch_method | varchar(16) | 'html'::character varying | false |  |  |  |
| follow_pagination | boolean | false | false |  |  |  |
| id | bigint |  | false | [public.chunks](public.chunks.md) [public.llm_calls](public.llm_calls.md) [public.scholarships](public.scholarships.md) [public.snapshots](public.snapshots.md) [public.sources](public.sources.md) |  |  |
| kind | varchar(16) |  | false |  |  |  |
| last_checked_at | timestamp with time zone |  | true |  |  |  |
| last_error | text |  | true |  |  |  |
| last_failed_on | date |  | true |  |  |  |
| last_page_count | integer |  | true |  |  |  |
| manual_reason | text |  | true |  |  |  |
| name | text |  | false |  |  |  |
| page_zero_is_first | boolean | false | false |  |  |  |
| parent_id | bigint |  | true |  | [public.sources](public.sources.md) |  |
| picked_at | timestamp with time zone |  | true |  |  |  |
| picked_urls | text[] | '{}'::text[] | false |  |  |  |
| retry_on | date |  | true |  |  |  |
| review_note | text |  | true |  |  |  |
| status | varchar(16) | 'approved'::character varying | false |  |  |  |
| unreachable_since | date |  | true |  |  |  |
| url | text |  | false |  |  |  |

## Constraints

| Name | Type | Definition |
| ---- | ---- | ---------- |
| sources_agent_run_id_fkey | FOREIGN KEY | FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL |
| sources_parent_id_fkey | FOREIGN KEY | FOREIGN KEY (parent_id) REFERENCES sources(id) |
| sources_pkey | PRIMARY KEY | PRIMARY KEY (id) |
| sources_url_key | UNIQUE | UNIQUE (url) |

## Indexes

| Name | Definition |
| ---- | ---------- |
| sources_pkey | CREATE UNIQUE INDEX sources_pkey ON public.sources USING btree (id) |
| sources_url_key | CREATE UNIQUE INDEX sources_url_key ON public.sources USING btree (url) |

## Relations

```mermaid
erDiagram

"public.sources" }o--o| "public.agent_runs" : "FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL"
"public.chunks" }o--|| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE"
"public.llm_calls" }o--o| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL"
"public.scholarships" }o--o| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id)"
"public.snapshots" }o--|| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id)"
"public.sources" }o--o| "public.sources" : "FOREIGN KEY (parent_id) REFERENCES sources(id)"

"public.sources" {
  bigint agent_run_id FK
  integer check_interval_hours
  text country
  timestamp_with_time_zone created_at
  timestamp_with_time_zone decided_at
  timestamp_with_time_zone disabled_at
  varchar_16_ discovery
  integer empty_extractions
  boolean enabled
  integer fail_days
  varchar_16_ fetch_method
  boolean follow_pagination
  bigint id
  varchar_16_ kind
  timestamp_with_time_zone last_checked_at
  text last_error
  date last_failed_on
  integer last_page_count
  text manual_reason
  text name
  boolean page_zero_is_first
  bigint parent_id FK
  timestamp_with_time_zone picked_at
  text__ picked_urls
  date retry_on
  text review_note
  varchar_16_ status
  date unreachable_since
  text url
}
"public.agent_runs" {
  double_precision cost_usd
  text final_text
  timestamp_with_time_zone finished_at
  bigint id
  varchar_16_ result
  timestamp_with_time_zone started_at
  integer steps
  varchar_256_ target
  varchar_32_ task
}
"public.chunks" {
  varchar_64_ content_hash
  text embed_model
  vector_1536_ embedding
  text__ heading_path
  bigint id
  varchar_8_ kind
  integer position
  bigint snapshot_id FK
  bigint source_id FK
  text summary
  text text
  text__ topics
}
"public.llm_calls" {
  bigint agent_run_id FK
  timestamp_with_time_zone called_at
  double_precision cost_usd
  text error
  varchar_64_ feature
  bigint id
  integer input_tokens
  varchar_64_ model
  integer output_tokens
  varchar_64_ prompt_version
  bigint run_id FK
  bigint source_id FK
}
"public.scholarships" {
  text amount
  text__ countries
  text coverage
  text__ degrees
  bigint duplicate_of FK
  varchar_64_ embed_hash
  text embed_model
  vector_1536_ embedding
  jsonb extracted
  text__ fields
  varchar_16_ how_to_apply
  bigint id
  text key
  text language_requirements
  timestamp_with_time_zone last_verified_at
  text name
  text name_zh
  text__ nationalities
  text nationality_conditions
  varchar_16_ nationality_scope
  varchar_32_ no_date_reason
  text official_url
  text other_eligibility
  text provider
  boolean requires_admission
  bigint source_id FK
  varchar_16_ status
}
"public.snapshots" {
  varchar_64_ content_hash
  text etag
  timestamp_with_time_zone fetched_at
  text file_path
  smallint http_status
  bigint id
  text last_modified
  timestamp_with_time_zone seen_at
  bigint source_id FK
  text url
}
```

---

> Generated by [tbls](https://github.com/k1LoW/tbls)
