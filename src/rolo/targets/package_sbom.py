from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.targets.bootstrap import (
    TARGET_PACKAGE_SBOM_NAME,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
MAX_TARGET_PACKAGE_SBOM_BYTES = 16 * 1024 * 1024


class TargetPackageSbomHash(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alg: Literal["SHA-256"] = "SHA-256"
    content: str = Field(pattern=_SHA256_PATTERN)


class TargetPackageSbomProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^rolo:[a-z0-9-]+$", max_length=128)
    value: str = Field(min_length=1, max_length=4096)


class TargetPackageSbomFileComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["file"] = "file"
    bom_ref: str = Field(alias="bom-ref", min_length=1, max_length=4112)
    name: str = Field(min_length=1, max_length=4096)
    hashes: list[TargetPackageSbomHash] = Field(min_length=1, max_length=1)
    properties: list[TargetPackageSbomProperty] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def require_canonical_component(self) -> TargetPackageSbomFileComponent:
        if self.bom_ref != f"file:{self.name}":
            raise ValueError("target package SBOM file bom-ref does not match its path")
        names = [item.name for item in self.properties]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("target package SBOM file properties are not canonical")
        return self


class TargetPackageSbomApplicationComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["application"] = "application"
    bom_ref: str = Field(alias="bom-ref", min_length=1, max_length=512)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    properties: list[TargetPackageSbomProperty] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def require_canonical_properties(self) -> TargetPackageSbomApplicationComponent:
        names = [item.name for item in self.properties]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("target package SBOM application properties are not canonical")
        return self


class TargetPackageSbomMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: TargetPackageSbomApplicationComponent


class TargetPackageSbom(BaseModel):
    """Strict deterministic CycloneDX 1.6 inventory for one signed target package."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    bom_format: Literal["CycloneDX"] = Field(default="CycloneDX", alias="bomFormat")
    spec_version: Literal["1.6"] = Field(default="1.6", alias="specVersion")
    version: Literal[1] = 1
    metadata: TargetPackageSbomMetadata
    components: list[TargetPackageSbomFileComponent] = Field(
        min_length=1,
        max_length=4096,
    )

    @model_validator(mode="after")
    def require_canonical_components(self) -> TargetPackageSbom:
        names = [item.name for item in self.components]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("target package SBOM components are not canonical")
        return self

    def document_json(self) -> str:
        return (
            json.dumps(
                self.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def _properties(values: dict[str, str]) -> list[TargetPackageSbomProperty]:
    return [
        TargetPackageSbomProperty(name=name, value=value)
        for name, value in sorted(values.items())
    ]


def build_target_package_sbom(manifest: TargetPackageManifest) -> TargetPackageSbom:
    components = [
        TargetPackageSbomFileComponent(
            bom_ref=f"file:{item.path}",
            name=item.path,
            hashes=[TargetPackageSbomHash(content=item.sha256)],
            properties=_properties(
                {
                    "rolo:mode": f"{item.mode:04o}",
                    "rolo:role": item.role.value,
                    "rolo:size-bytes": str(item.size_bytes),
                }
            ),
        )
        for item in manifest.files
        if item.role != TargetPackageFileRole.SBOM
    ]
    return TargetPackageSbom(
        metadata=TargetPackageSbomMetadata(
            component=TargetPackageSbomApplicationComponent(
                bom_ref=(
                    f"pkg:generic/{manifest.package_id}@{manifest.package_version}"
                    f"?arch={manifest.architecture.value}"
                ),
                name=manifest.package_id,
                version=manifest.package_version,
                properties=_properties(
                    {
                        "rolo:architecture": manifest.architecture.value,
                        "rolo:python-requires": manifest.python_requires,
                        "rolo:target-os": manifest.target_os,
                        "rolo:version": manifest.rolo_version,
                    }
                ),
            )
        ),
        components=components,
    )


def bind_target_package_sbom(
    manifest: TargetPackageManifest,
) -> tuple[TargetPackageManifest, TargetPackageSbom, bytes]:
    if any(item.role == TargetPackageFileRole.SBOM for item in manifest.files):
        raise ValueError("target package manifest already declares an SBOM")
    sbom = build_target_package_sbom(manifest)
    payload = sbom.document_json().encode("utf-8")
    if len(payload) > MAX_TARGET_PACKAGE_SBOM_BYTES:
        raise ValueError("target package SBOM exceeded its size limit")
    descriptor = TargetPackageFile(
        path=TARGET_PACKAGE_SBOM_NAME,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        mode=0o644,
        role=TargetPackageFileRole.SBOM,
    )
    bound = TargetPackageManifest(
        **{
            **manifest.model_dump(mode="python", exclude={"files"}),
            "files": sorted([*manifest.files, descriptor], key=lambda item: item.path),
        }
    )
    return bound, sbom, payload


def verify_target_package_sbom(
    manifest: TargetPackageManifest,
    sbom: TargetPackageSbom,
) -> None:
    declared = [
        item for item in manifest.files if item.role == TargetPackageFileRole.SBOM
    ]
    if len(declared) != 1 or declared[0].path != TARGET_PACKAGE_SBOM_NAME:
        raise ValueError("target package does not declare one canonical SBOM")
    if sbom != build_target_package_sbom(manifest):
        raise ValueError("target package SBOM does not match its signed manifest")
