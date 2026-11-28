# scholar

## Tables

| Name | Columns | Comment | Type |
| ---- | ------- | ------- | ---- |
| [public.agent_runs](public.agent_runs.md) | 9 |  | BASE TABLE |
| [public.agent_steps](public.agent_steps.md) | 11 |  | BASE TABLE |
| [public.app_settings](public.app_settings.md) | 4 |  | BASE TABLE |
| [public.breakers](public.breakers.md) | 4 |  | BASE TABLE |
| [public.changes](public.changes.md) | 7 |  | BASE TABLE |
| [public.chunks](public.chunks.md) | 12 |  | BASE TABLE |
| [public.cycles](public.cycles.md) | 16 |  | BASE TABLE |
| [public.events](public.events.md) | 11 |  | BASE TABLE |
| [public.llm_calls](public.llm_calls.md) | 12 |  | BASE TABLE |
| [public.matches](public.matches.md) | 15 |  | BASE TABLE |
| [public.profiles](public.profiles.md) | 9 |  | BASE TABLE |
| [public.requirements](public.requirements.md) | 8 |  | BASE TABLE |
| [public.runs](public.runs.md) | 5 |  | BASE TABLE |
| [public.scholarship_categories](public.scholarship_categories.md) | 9 |  | BASE TABLE |
| [public.scholarships](public.scholarships.md) | 27 |  | BASE TABLE |
| [public.snapshots](public.snapshots.md) | 10 |  | BASE TABLE |
| [public.sources](public.sources.md) | 29 |  | BASE TABLE |
| [public.universities](public.universities.md) | 9 |  | BASE TABLE |

## Relations

```mermaid
erDiagram

"public.agent_steps" }o--|| "public.agent_runs" : "FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE CASCADE"
"public.changes" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.changes" }o--o| "public.snapshots" : "FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL"
"public.chunks" }o--|| "public.snapshots" : "FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE"
"public.chunks" }o--|| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE"
"public.cycles" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.events" }o--o| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.llm_calls" }o--o| "public.agent_runs" : "FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL"
"public.llm_calls" }o--o| "public.runs" : "FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL"
"public.llm_calls" }o--o| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL"
"public.matches" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.requirements" }o--o| "public.scholarship_categories" : "FOREIGN KEY (category_id) REFERENCES scholarship_categories(id) ON DELETE CASCADE"
"public.requirements" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.scholarship_categories" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.scholarships" }o--o| "public.scholarships" : "FOREIGN KEY (duplicate_of) REFERENCES scholarships(id) ON DELETE SET NULL"
"public.scholarships" }o--o| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id)"
"public.snapshots" }o--|| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id)"
"public.sources" }o--o| "public.agent_runs" : "FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL"
"public.sources" }o--o| "public.sources" : "FOREIGN KEY (parent_id) REFERENCES sources(id)"

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
"public.agent_steps" {
  bigint agent_run_id FK
  jsonb args
  timestamp_with_time_zone created_at
  text full_text
  bigint id
  integer input_tokens
  varchar_8_ kind
  integer number
  integer output_tokens
  text summary
  varchar_64_ tool
}
"public.app_settings" {
  bigint id
  double_precision monthly_cap_ntd
  integer notify_threshold
  bigint user_id
}
"public.breakers" {
  bigint id
  varchar_32_ name
  timestamp_with_time_zone opened_at
  text reason
}
"public.changes" {
  timestamp_with_time_zone changed_at
  text field
  bigint id
  jsonb new_value
  jsonb old_value
  bigint scholarship_id FK
  bigint snapshot_id FK
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
"public.cycles" {
  timestamp_with_time_zone closes_at
  boolean estimated
  text evidence
  varchar_16_ funding
  bigint id
  text intake
  text label
  text__ nationalities
  varchar_16_ nationality_scope
  timestamp_with_time_zone opens_at
  date recheck_from
  bigint scholarship_id FK
  varchar_16_ status
  text timezone
  boolean timezone_assumed
  varchar_32_ verification
}
"public.events" {
  integer attempts
  timestamp_with_time_zone created_at
  text dedup_key
  bigint id
  varchar_32_ kind
  text last_error
  jsonb payload
  bigint scholarship_id FK
  timestamp_with_time_zone sent_at
  varchar_16_ status
  bigint user_id
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
"public.matches" {
  integer cap
  text category_name
  jsonb checks
  timestamp_with_time_zone computed_at
  text__ failed
  bigint id
  varchar_64_ input_hash
  text model
  integer profile_version
  text prompt_version
  bigint scholarship_id FK
  jsonb sub_scores
  double_precision total
  text__ unclear
  bigint user_id
}
"public.profiles" {
  text current_major
  bigint id
  varchar_2_ nationality
  varchar_2___ target_countries
  varchar_16_ target_degree
  text__ target_fields
  timestamp_with_time_zone updated_at
  bigint user_id
  integer version
}
"public.requirements" {
  bigint category_id FK
  integer count
  text details
  varchar_32_ doc_type
  text evidence
  bigint id
  boolean required
  bigint scholarship_id FK
}
"public.runs" {
  jsonb counts
  timestamp_with_time_zone finished_at
  bigint id
  date local_date
  timestamp_with_time_zone started_at
}
"public.scholarship_categories" {
  text amount
  text__ countries
  text degree_conditions
  text__ degrees
  text eligibility
  bigint id
  text name
  integer quota
  bigint scholarship_id FK
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
"public.universities" {
  varchar_2_ country
  text homepage
  bigint id
  varchar_32_ last_result
  timestamp_with_time_zone last_searched_at
  text name
  text note
  varchar_32_ region
  text source_url
}
```

---

> Generated by [tbls](https://github.com/k1LoW/tbls)
