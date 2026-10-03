# Run summary - cycle 2026-09 (dry-run)

- Started: 2026-09-14T20:35:22+00:00
- Finished: 2026-09-14T20:35:24+00:00
- Production: `demo/DirectoryQualityHub.sqlite`
- Production hash before / after: `c9ef321fba09` / `-`
- Final status: **dry run (NOT READY)**

## Backup

- `demo/backups/DirectoryQualityHub_2026-09_<run>.sqlite`
- verified: True  (sha256 `c9ef321fba09`)

## Stages

| stage | status | summary |
|---|---|---|
| preflight | completed | databases=3; repository_tables=6; repository_rows=24727; saved_queries=24; rules=22; problems=0 |
| backup | completed | backup=demo/backups/DirectoryQualityHub_2026-09_<run>.sqlite; size=5894144; verified=True; retained=2; pruned=0 |
| transfer | completed | transfers=4; completed=4; skipped=0; failed=0; rows_loaded=25642 |
| professional_duplicates | completed | candidate_rows=513; groups=250; groups_exact=150; groups_legitimate=40; groups_review=60; decided_from_log=0; deleted=163; remaining_rows=200; unresolved_groups=60 |
| service_cleanup | completed | rows_before=5616; rows_after=5450; deleted_total=166; approved_deletions=31; retired_source:LegacyVendorFeed=135 |
| service_duplicates | completed | service_address_candidate_rows=300; service_address_groups=150; service_address_deleted=80; service_address_remaining_rows=140; service_address_unresolved_groups=30; service_phone_candidate_rows=2571; service_phone_groups=945; service_phone_deleted=0; service_phone_remaining_rows=2571; service_phone_unresolved_groups=66; deleted=80; unresolved_groups=96 |
| line_codes | completed | ProfessionalDirectory_populated=19082; ProfessionalDirectory_partial=60; ServiceDirectory_populated=5225; ServiceDirectory_partial=44; populated=24307; left_blank_all_flags_blank=477; needs_rule_partial_flags=104 |
| pharmacy_languages | completed | malformed_found=210; changed=210; became_blank=31; remaining_malformed=0 |
| quality_checks | completed | rules=22; status_fail=9; status_pass=3; status_reminder=1; status_report=5; status_warn=4; blocking_failures=9; unaccepted_blocking_failures=9; checklist_CLEAR=1; checklist_HIGH=4; checklist_REMINDER=1; checklist_REVIEW=3 |
| comparison | completed | ProfessionalDirectory_prior=19202; ProfessionalDirectory_current=19518; ServiceDirectory_prior=4572; ServiceDirectory_current=5370; flagged_sources=1 |
| readiness | completed | verdict=NOT READY; checks=11; failing=4; advisory_open=4; accepted=0 |
| promote | dry-run | would_promote=False; readiness=NOT READY |

## Notes

- **backup**: restores the state before cycle 2026-09: demo/backups/DirectoryQualityHub_2026-09_<run>.sqlite
- **service_duplicates**: phone duplicates were reviewed after address deletions, so their count already excludes rows the address step removed
- **line_codes**: 104 rows have some but not all flags; no code was written for them - they need a business rule
- **quality_checks**: BLOCKING missing_service_geography: 70 rows returned
- **quality_checks**: BLOCKING missing_provider_county: 120 rows returned
- **quality_checks**: BLOCKING missing_provider_specialty: 60 rows returned
- **quality_checks**: BLOCKING missing_provider_phone: 90 rows returned
- **quality_checks**: BLOCKING invalid_specialty_county: 40 rows returned
- **quality_checks**: BLOCKING missing_school_limitation: 30 rows returned
- **quality_checks**: BLOCKING named_exclusion_present: 2 rows returned
- **quality_checks**: BLOCKING vision_island_presence: absent
- **quality_checks**: BLOCKING vision_line_a_required: 12 rows returned
- **comparison**: ServiceDirectory/CommunityCareFeed: +300.0% (225 -> 900); rows per location rose 1.0 -> 4.0: row expansion across service lines, not new locations (225 -> 225)
- **readiness**: stopped before borough generation - that phase is manual by design
- **promote**: production untouched. To promote: rerun with --apply --authorize "APPLY 2026-09 TO DirectoryQualityHub.sqlite"

## Readiness

**NOT READY**

- [x] final table counts recorded: ProfessionalDirectory=19,518; ServiceDirectory=5,370; PharmacyPublicationDirectory=600; OtherFacilityReference=197; ManagedCareFacilitySource=148; ApprovedDeletionList=12
- [x] preflight completed: completed
- [x] backup completed: completed
- [x] transfer completed: completed
- [ ] duplicate review professional: no unresolved groups: 200 rows still returned by the official query; 60 groups need a decision
- [ ] duplicate review service_address: no unresolved groups: 140 rows still returned by the official query; 30 groups need a decision
- [ ] duplicate review service_phone: no unresolved groups: 2571 rows still returned by the official query; 66 groups need a decision
- [ ] blocking checks clear or accepted: missing_service_geography (70 rows returned), missing_provider_county (120 rows returned), missing_provider_specialty (60 rows returned), missing_provider_phone (90 rows returned), invalid_specialty_county (40 rows returned), missing_school_limitation (30 rows returned), named_exclusion_present (2 rows returned), vision_island_presence (absent), vision_line_a_required (12 rows returned)
- [x] pharmacy language QA clear: 0 malformed values remain
- [x] line codes populated: 24307 populated; 104 need a rule
- [x] retired source LegacyVendorFeed absent: 0 rows

## Evidence files

- `evidence/preflight.json`
- `evidence/transfer.json`
- `evidence/duplicates_professional_rows.csv`
- `evidence/duplicates_professional_groups.csv`
- `evidence/cleanup_approved_deletions.csv`
- `evidence/cleanup_retired_source_LegacyVendorFeed.csv`
- `evidence/duplicates_service_address_rows.csv`
- `evidence/duplicates_service_address_groups.csv`
- `evidence/duplicates_service_phone_rows.csv`
- `evidence/duplicates_service_phone_groups.csv`
- `evidence/line_codes_ProfessionalDirectory_needs_rule.csv`
- `evidence/line_codes_ProfessionalDirectory_review.csv`
- `evidence/line_codes_ServiceDirectory_needs_rule.csv`
- `evidence/line_codes_ServiceDirectory_review.csv`
- `evidence/pharmacy_language_changes.csv`
- `evidence/rule_results.csv`
- `evidence/rule_missing_service_geography.csv`
- `evidence/rule_missing_provider_county.csv`
- `evidence/rule_missing_provider_specialty.csv`
- `evidence/rule_missing_provider_phone.csv`
- `evidence/rule_invalid_specialty_county.csv`
- `evidence/rule_missing_school_limitation.csv`
- `evidence/rule_named_exclusion_present.csv`
- `evidence/rule_vision_line_a_required.csv`
- `evidence/rule_named_org_nonzero_lines.csv`
- `evidence/rule_vision_presentation_review.csv`
- `evidence/rule_zip_borough_mismatch.csv`
- `evidence/rule_partial_flags.csv`
- `evidence/rule_hospital_network_line_counts.csv`
- `evidence/rule_behavioral_health_type_counts.csv`
- `evidence/rule_core_service_line_combinations.csv`
- `evidence/rule_vision_listings.csv`
- `evidence/rule_vision_rows_by_borough.csv`
- `evidence/checklist_classification.csv`
- `evidence/comparison_ProfessionalDirectory.csv`
- `evidence/comparison_ProfessionalDirectory_by_location.csv`
- `evidence/comparison_ServiceDirectory.csv`
- `evidence/comparison_ServiceDirectory_by_location.csv`
- `evidence/readiness.json`

---
Borough generation was **not** run. It is a separate, manual phase.
