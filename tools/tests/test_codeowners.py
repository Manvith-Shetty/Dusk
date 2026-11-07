from duskctl.codeowners import CodeOwners

SAMPLE = """
# comment
*                       @org/default
*.js                    @org/frontend
/docs/                  @org/docs
/docs/*                 @org/docs-root-only
/pkg/api/               @org/backend
/pkg/api/legacy/        @org/legacy
/pkg/services/ngalert/  @org/alerting
apps/                   @org/apps-anywhere
/scripts/ci-*           @org/ci
/packages/data/src/**/*logs*  @org/logs
/go.mod
/pkg/router             @org/router @org/second
"""


def owners(path):
    return CodeOwners.from_text(SAMPLE).owners_of(path)


def test_last_match_wins_over_specificity():
    # /pkg/api/legacy/ is listed after /pkg/api/ so it wins; the reverse order would not.
    assert owners("pkg/api/legacy/x.go") == ("@org/legacy",)
    assert owners("pkg/api/x.go") == ("@org/backend",)


def test_catch_all_and_extension():
    assert owners("README.md") == ("@org/default",)
    assert owners("public/app/x.js") == ("@org/frontend",)


def test_directory_vs_direct_children():
    # `/docs/*` is listed after `/docs/` so it wins for direct children only.
    assert owners("docs/intro.md") == ("@org/docs-root-only",)
    assert owners("docs/sub/deep.md") == ("@org/docs",)


def test_unanchored_directory_matches_anywhere():
    assert owners("apps/web/x.ts") == ("@org/apps-anywhere",)
    assert owners("src/apps/web/x.ts") == ("@org/apps-anywhere",)


def test_star_within_segment():
    assert owners("scripts/ci-build.sh") == ("@org/ci",)
    # A wildcard final segment names direct children only, like `/docs/*`.
    assert owners("scripts/ci-build/nested.sh") == ("@org/default",)
    assert owners("scripts/other.sh") == ("@org/default",)


def test_double_star():
    assert owners("packages/data/src/a/b/logs_util.ts") == ("@org/logs",)
    assert owners("packages/data/src/mylogs.ts") == ("@org/logs",)


def test_no_owner_unsets():
    assert owners("go.mod") == ()


def test_directory_pattern_without_trailing_slash_owns_contents():
    assert owners("pkg/router/r.go") == ("@org/router", "@org/second")
    assert owners("pkg/router") == ("@org/router", "@org/second")


def test_alerting_subtree():
    assert owners("pkg/services/ngalert/api/x.go") == ("@org/alerting",)
    assert owners("pkg/services/other/x.go") == ("@org/default",)


def test_teams_listing_is_ordered_and_unique():
    co = CodeOwners.from_text(SAMPLE)
    assert co.teams()[0] == "@org/default"
    assert len(co.teams()) == len(set(co.teams()))
