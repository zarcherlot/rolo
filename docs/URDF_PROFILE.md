# URDF enrollment profile

`robotctl init --robot-id ...` registers identity only. It does not accept, read, or record a URDF.

The initial URDF state is `NOT_DISCOVERED`, semantic state is `UNRESOLVED`, and motion safety state
is `UNAPPROVED`. `robotctl discover run --robot ... --urdf /path/to/robot.urdf` loads the file and
performs the full parsing described below. Its artifact records the resolved path and SHA-256.

## Discovery-time standard URDF data

rolo validates and reads:

- the `<robot name>` as the internal `profile_id`;
- named links and joints;
- the configured base link's box or cylinder collision geometry as the footprint, when available;
- joint `<limit velocity>` values;
- sensor link references.

Mesh bounds are not inferred. Missing or mesh-only footprint geometry is recorded as unresolved
rather than guessed.

## Optional rolo extension

Standard URDF does not define mobile-base maximum linear/angular velocity or rolo sensor semantics.
When known, these values can be declared in an optional `<rolo>` element:

```xml
<rolo
  drive_model="differential"
  base_link="base_link"
  hard_max_linear_velocity_mps="0.8"
  hard_max_angular_velocity_radps="1.5">
  <sensor name="front_camera" link="front_camera_link"
    semantic_uri="semantic://sensor/front_camera" modality="camera_rgb"/>
  <feature name="navigation_2d" enabled="true"/>
</rolo>
```

`drive_model` currently accepts `differential` or `ackermann`. Declared hard limits must be
positive, and every declared sensor must reference an existing URDF link. Files containing
DTD/entity declarations, invalid XML, invalid declared values, or unresolved declared sensor links
are rejected. A valid structural URDF without `<rolo>`, footprint, drive model, or mobile-base speed
limits is accepted; those fields are stored in `features.enrollment.unresolved_semantics`.

## Discovery and agent input

During source discovery, rolo statically scans launch and configuration files for common parameter
names such as `max_vel_x`, `max_linear_velocity`, `max_vel_theta`, and
`max_angular_velocity`. It does not execute those files. Every extracted value records its canonical
field, unit, source path, original key, and `DISCOVERED_UNVERIFIED` status in
`semantic_context.json`.

The unresolved fields and candidates are copied into the Build, Debug, and Test agent inputs.
Speed values declared in the optional URDF extension are also represented as
`DECLARED_UNVERIFIED` with `safety_authority: none`; a declaration is evidence, not approval.
Source candidates may describe a controller setting rather than a physical safety limit, so they
always carry `safety_authority: none`. Agents may use them to guide implementation, diagnosis, and
controlled validation, but they must not silently promote them to verified hard motion limits.

## Registration and approval

Initialization records no URDF data. Each discovery run records the supplied absolute URDF path and
SHA-256 with its evidence. There is no installation-time safety confirmation because no URDF has
been supplied at that point. Motion remains `UNAPPROVED` until a later
controlled debug/test validation and explicit safety-approval workflow promotes it.

See [`differential_drive.urdf`](../configs/profiles/differential_drive.urdf) and
[`ackermann.urdf`](../configs/profiles/ackermann.urdf) for complete format examples.
