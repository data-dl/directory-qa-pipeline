# Decision log

One CSV per duplicate review (`professional.csv`, `service_address.csv`,
`service_phone.csv`). Each row records a person's decision about one group that
the pipeline could not resolve on its own.

| column | meaning |
|---|---|
| `group_hash` | copied from `duplicates_<name>_groups.csv` in a run's evidence folder |
| `decision` | `delete` (keep one row, remove the rest), `exception` (they are different listings; keep all), or `keep` (leave as is for now) |
| `keep_stable_key` | for `delete`: the stable key of the row to keep; blank keeps the lowest record id |
| `decided_by`, `decided_on`, `note` | who, when, why |

The hash covers the fields the review compares, not the record ids, so a group
that returns unchanged next month gets the same decision applied automatically
and one that changed is surfaced again. Nothing in these files can delete a row
the pipeline classified as `legitimate`.
