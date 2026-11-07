**20 call sites** of `pkg/bus` in **20 files** across **7 teams**, found in 27.3 s (commit `87a1a1deb8`, owners from `.github/CODEOWNERS`).

| Team | Files | Call sites | Where |
|---|---:|---:|---|
| @grafana/grafana-backend-services-squad | 7 | 7 | `pkg/api/http_server.go`, `pkg/server/bootstrap/wire/sets.go`, `pkg/server/bootstrap/wire/wire_gen.go`, `pkg/server/wire_core.go` +3 more |
| @grafana/alerting-squad | 4 | 4 | `pkg/services/ngalert/ngalert.go`, `pkg/services/ngalert/store/folderlabelsyncer/service.go`, `pkg/services/ngalert/tests/util.go`, `pkg/services/ngalert/testutil/testutil.go` |
| @grafana/grafana-search-and-storage | 4 | 4 | `pkg/services/sqlstore/sqlstore.go`, `pkg/services/sqlstore/sqlstore_testinfra.go`, `pkg/services/sqlstore/transactions.go`, `pkg/storage/legacysql/legacywatch/publisher.go` |
| @grafana/datapro | 2 | 2 | `pkg/services/correlations/correlationstest/fake.go`, `pkg/services/correlations/provider.go` |
| @grafana/grafana-catalog | 1 | 1 | `pkg/services/plugindashboards/service/dashboard_updater.go` |
| @grafana/grafana-operator-experience-squad | 1 | 1 | `pkg/extensions/enterprise_imports.go` |
| @grafana/identity-squad | 1 | 1 | `pkg/services/serviceaccounts/extsvcaccounts/service.go` |