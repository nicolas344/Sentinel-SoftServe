POST_MORTEM_TEMPLATE = (
    "# Post-Mortem: {title}\n\n"
    "## Summary\n{summary}\n\n"
    "## Root Cause\n{root_cause}\n\n"
    "## Timeline\n{timeline}\n\n"
    "## Resolution\n{resolution}\n\n"
    "## MTTR\n{mttr}\n\n"
    "## Lessons Learned\n{lessons_learned}\n\n"
    "## Preventive Actions\n{preventive_actions}\n"
)


def render_post_mortem_template(
    *,
    title: str,
    summary: str,
    root_cause: str,
    timeline: str,
    resolution: str,
    mttr: str,
    lessons_learned: str,
    preventive_actions: str,
) -> str:
    return POST_MORTEM_TEMPLATE.format(
        title=title,
        summary=summary,
        root_cause=root_cause,
        timeline=timeline,
        resolution=resolution,
        mttr=mttr,
        lessons_learned=lessons_learned,
        preventive_actions=preventive_actions,
    )
