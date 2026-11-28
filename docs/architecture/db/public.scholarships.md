# public.scholarships

## Columns

| Name | Type | Default | Nullable | Children | Parents | Comment |
| ---- | ---- | ------- | -------- | -------- | ------- | ------- |
| amount | text |  | true |  |  |  |
| countries | text[] | '{}'::text[] | false |  |  |  |
| coverage | text |  | true |  |  |  |
| degrees | text[] | '{}'::text[] | false |  |  |  |
| duplicate_of | bigint |  | true |  | [public.scholarships](public.scholarships.md) |  |
| embed_hash | varchar(64) |  | true |  |  |  |
| embed_model | text |  | true |  |  |  |
| embedding | vector(1536) |  | true |  |  |  |
| extracted | jsonb |  | false |  |  |  |
| fields | text[] | '{}'::text[] | false |  |  |  |
| how_to_apply | varchar(16) |  | true |  |  |  |
| id | bigint |  | false | [public.changes](public.changes.md) [public.cycles](public.cycles.md) [public.events](public.events.md) [public.matches](public.matches.md) [public.requirements](public.requirements.md) [public.scholarship_categories](public.scholarship_categories.md) [public.scholarships](public.scholarships.md) |  |  |
| key | text | 'main'::text | false |  |  |  |
| language_requirements | text |  | true |  |  |  |
| last_verified_at | timestamp with time zone |  | true |  |  |  |
| name | text |  | false |  |  |  |
| name_zh | text |  | true |  |  |  |
| nationalities | text[] | '{}'::text[] | false |  |  |  |
| nationality_conditions | text |  | true |  |  |  |
| nationality_scope | varchar(16) | 'unclear'::character varying | false |  |  |  |
| no_date_reason | varchar(32) |  | true |  |  |  |
| official_url | text |  | true |  |  |  |
| other_eligibility | text |  | true |  |  |  |
| provider | text |  | true |  |  |  |
| requires_admission | boolean |  | true |  |  |  |
| source_id | bigint |  | true |  | [public.sources](public.sources.md) |  |
| status | varchar(16) | 'active'::character varying | false |  |  |  |

## Constraints

| Name | Type | Definition |
| ---- | ---- | ---------- |
| scholarships_duplicate_of_fkey | FOREIGN KEY | FOREIGN KEY (duplicate_of) REFERENCES scholarships(id) ON DELETE SET NULL |
| scholarships_pkey | PRIMARY KEY | PRIMARY KEY (id) |
| scholarships_source_id_fkey | FOREIGN KEY | FOREIGN KEY (source_id) REFERENCES sources(id) |
| scholarships_source_id_key_key | UNIQUE | UNIQUE (source_id, key) |

## Indexes

| Name | Definition |
| ---- | ---------- |
| scholarships_pkey | CREATE UNIQUE INDEX scholarships_pkey ON public.scholarships USING btree (id) |
| scholarships_source_id_key_key | CREATE UNIQUE INDEX scholarships_source_id_key_key ON public.scholarships USING btree (source_id, key) |

## Relations

```mermaid
erDiagram

"public.scholarships" }o--o| "public.scholarships" : "FOREIGN KEY (duplicate_of) REFERENCES scholarships(id) ON DELETE SET NULL"
"public.changes" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.cycles" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.events" }o--o| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.matches" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.requirements" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.scholarship_categories" }o--|| "public.scholarships" : "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
"public.scholarships" }o--o| "public.sources" : "FOREIGN KEY (source_id) REFERENCES sources(id)"

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
"public.changes" {
  timestamp_with_time_zone changed_at
  text field
  bigint id
  jsonb new_value
  jsonb old_value
  bigint scholarship_id FK
  bigint snapshot_id FK
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
```

---

> Generated by [tbls](https://github.com/k1LoW/tbls)
