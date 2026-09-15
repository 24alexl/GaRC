from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


NodeType = Literal["device", "server", "storage", "data_asset", "firewall", "user", "subnet", "cloud_service"]
RelationshipType = Literal["MEMBER_OF", "LOGS_IN_VIA", "ROUTES_TO", "ACCESSES", "STORES", "PROTECTS", "STORES_CUI"]

class NetworkNode(BaseModel):
    model_config = {"extra": "ignore"}
    id: str = Field(description="Unique node identifier e.g. dev_workstation_1, nas_storage, firewall_gateway")
    name: str = Field(description="Human readable name e.g. Office NAS, Windows Admin PC")
    type: str = Field(description="Node type: device, server, storage, data_asset, firewall, user, subnet, cloud_service")
    os_or_system: Optional[str] = Field(default="Unknown", description="Operating system or system software")
    ip_or_subnet: Optional[str] = Field(default="Unknown", description="IP address or CIDR subnet")
    stores_cui: bool = Field(default=False, description="Whether this node processes or stores Controlled Unclassified Information (CUI)")
    has_firewall_or_mfa: bool = Field(default=False, description="Whether firewall or MFA is confirmed on this asset")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score from 0.0 to 1.0")

class NetworkEdge(BaseModel):
    model_config = {"extra": "ignore"}
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    relationship: str = Field(description="Relationship type: MEMBER_OF, LOGS_IN_VIA, ROUTES_TO, ACCESSES, STORES, PROTECTS, STORES_CUI")
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

class KGTraceItem(BaseModel):
    id: str  # e.g. "3.1.1", "cui_database", "guest_wifi -> cui_db"
    label: str  # e.g. "3.1.1 Authorized Access Control", "CUI Database"
    type: str  # "control" | "node" | "edge"
    family: Optional[str] = None  # e.g. "03.01", "03.05", "03.08", "03.13", "03.14"
    status: Optional[str] = None  # "MET" | "UNMET" | "NEEDS_INFO" | "ACTIVE"
    description: Optional[str] = None

class CopilotChatMessage(BaseModel):
    role: str = "user"  # "user" or "assistant"
    content: str
    kg_traces: List[KGTraceItem] = Field(default_factory=list)

class CopilotChatRequest(BaseModel):
    message: str
    history: List[CopilotChatMessage] = Field(default_factory=list)
    current_nodes: Optional[List[Dict[str, Any]]] = None
    current_edges: Optional[List[Dict[str, Any]]] = None

class CopilotChatResponse(BaseModel):
    reply: str
    actions_taken: List[str] = Field(default_factory=list)
    topology_updated: bool = False
    topology: Optional[Dict[str, Any]] = None
    suggested_followups: List[str] = Field(default_factory=list)
    kg_traces: List[KGTraceItem] = Field(default_factory=list)

class WhatIfSimulateRequest(BaseModel):
    fix_type: str = Field(description="e.g. ENCRYPT_CUI_VOLUME, ENFORCE_MFA, SEGMENT_GUEST_WIFI, DEPLOY_FIREWALL")
    target_node_id: Optional[str] = None

class WhatIfSimulateResponse(BaseModel):
    success: bool
    fix_title: str
    description: str
    score_before: float
    score_after: float
    score_delta: float
    active_fixes: List[str] = Field(default_factory=list)
    audit_result: Dict[str, Any]
    topology: Dict[str, Any]

