from agent_skills_manager.tui.grouping import group_skill_names


def test_repeated_prefixes_become_collapsible_families() -> None:
    groups = group_skill_names(
        [
            "gsd-plan",
            "gsd-review",
            "gsap-core",
            "gsap-react",
            "standalone",
            ".system",
        ]
    )

    assert [(group.key, group.names) for group in groups] == [
        ("gsap-", ("gsap-core", "gsap-react")),
        ("gsd-", ("gsd-plan", "gsd-review")),
        ("other", ("standalone",)),
    ]


def test_single_prefix_member_stays_in_other_group() -> None:
    groups = group_skill_names(["one-alpha", "plain"])

    assert len(groups) == 1
    assert groups[0].key == "other"
    assert groups[0].names == ("one-alpha", "plain")
