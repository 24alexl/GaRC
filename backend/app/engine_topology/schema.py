from typing import List, Optional
from pydantic import BaseModel, Field

class NetworkNode(BaseModel):
    id: str = Field(description="Unique node identifier e.g. dev_workstation_1, nas_storage, firewall_gateway")
    name: str = Field(description="Human readable name e.g. Office NAS, Windows Admin PC")
    type: str = Field(description="Node type: device, server, storage, firewall, user, subnet, cloud_service")
    os_or_system: Optional[str] = Field(default="Unknown", description="Operating system or system software")
    ip_or_subnet: Optional[str] = Field(default="Unknown", description="IP address or CIDR subnet")
    stores_cui: bool = Field(default=False, description="Whether this node processes or stores Controlled Unclassified Information (CUI)")
    has_firewall_or_mfa: bool = Field(default=False, description="Whether firewall or MFA is confirmed on this asset")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score from 0.0 to 1.0")

class NetworkEdge(BaseModel):
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    relationship: str = Field(description="Relationship type: CONNECTS_TO, ACCESSES, STORES, PROTECTS")
    is_encrypted: bool = Field(default=False, description="Whether connection is encrypted (TLS/VPN)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship extraction confidence score")

class ClarificationPrompt(BaseModel):
    node_id: Optional[str] = None
    edge: Optional[str] = None
    question: str
    property_in_question: str
    suggested_options: List[str]

class TopologyParseResult(BaseModel):
    raw_text: str
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    confidence_score: float
    requires_clarification: bool
    clarification_prompts: List[ClarificationPrompt]
