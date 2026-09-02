<!-- status: archived; authority: reference; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# Retired registry guide

The former canonical operation registry and its large platform-specific vocabulary are retired
in Rolo v2. This page is retained only so historical links resolve; it is not an implementation
requirement and no compatibility layer is shipped.

The v2 standard has four platform-neutral semantic families:

- `hardware`: physical inventory and presence observation;
- `OS`: host, process, service, resource and file observation;
- `Middleware`: graph, channel, topology and runtime observation;
- `application`: explicitly allowlisted application self-description.

An Agent may use a target's native interfaces directly when it can do so safely. Rolo adds a
Tool or Adapter only for a demonstrated gap, after bounded target evidence and independent
Conformance. See [Agent-native Tools](../adapt/AGENT_NATIVE_TOOLS.md) and the
[implementation map](../reference/IMPLEMENTATION_MAP.md).
