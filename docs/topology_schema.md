# GaRC Network Topology Schema & Relationship Reference

This document defines the formal taxonomy of **Node Types**, **Edge Relationship Schemes**, **Security Attributes**, and **Clarification Card Rules** utilized by GaRC (Engine 2) to translate natural language network descriptions into Cytoscape-renderable graphs and GraphRAG audit contexts.

---

## 1. Node Taxonomy (`NodeType`)

Nodes represent discrete computational assets, network boundaries, storage repositories, or user groups within an organization's architecture.

| Node Type | Description | Examples |
| :--- | :--- | :--- |
| `device` | End-user client devices, laptops, desktops, or mobile endpoints. | *Dell Laptops, Windows 11 PCs, Workstations* |
| `server` | On-premise physical or virtual server hosts. | *Windows Server 2022, Linux Host, Domain Controller* |
| `storage` | Hardware storage appliances, Network Attached Storage (NAS), or Database engines. | *TrueNAS Volume, Synology NAS, PostgreSQL Server* |
| `data_asset` | Logical files, datasets, volume shares, or CUI document repositories hosted on storage/servers. | *Payroll Contracts, Client CUI Files, Financial Records* |
| `firewall` | Network security gateways, hardware firewalls, or perimeter routers. | *pfSense, FortiGate, Edge Router* |
| `user` | Human user cohorts, employee groups, or external roles accessing the network. | *Remote Accountants, Staff, Admin Team* |
| `subnet` | Logical IP subnets, Local Area Networks (LAN), or virtual networks. | *192.168.1.0/24, On-Prem LAN, Management Subnet* |
| `cloud_service` | Cloud infrastructure, VPN gateways, object storage, or SaaS environments. | *AWS Cloud Storage, OpenVPN Gateway, Azure Enclave* |

---

## 2. Edge Relationship Taxonomy (`RelationshipType`)

Relationships define how traffic, data access, security boundaries, and host ownership flow between nodes.

```
[Device / User]  --(MEMBER_OF / LOGS_IN_VIA)-->  [Subnet / Gateway]
[Subnet / Gateway]  --------(ROUTES_TO / PROTECTS)------->  [Server / Cloud]
[Server / Host]  --------------(STORES)------------->  [Data Asset / CUI]
```

### Supported Relationship Types

| Relationship Type | Source Node | Target Node | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `MEMBER_OF` | `device`, `user`, `server` | `subnet` | Indicates physical or logical membership in an IP subnet/LAN. | *Laptops `MEMBER_OF` LAN Subnet* |
| `LOGS_IN_VIA` | `user`, `device` | `cloud_service`, `firewall` | Remote authentication path via VPN, SAML, or Gateway. | *Remote Staff `LOGS_IN_VIA` OpenVPN* |
| `ROUTES_TO` | `firewall`, `cloud_service` | `server`, `storage`, `cloud_service` | Network gateway routing traffic to downstream assets/cloud. | *OpenVPN `ROUTES_TO` AWS Cloud Storage* |
| `ACCESSES` | `device`, `user` | `server`, `storage`, `data_asset` | Direct network or application access to a server or share. | *Dell Laptops `ACCESSES` Windows Server 2022* |
| `STORES` | `server`, `storage`, `cloud_service` | `data_asset` | Hosting node containing files, databases, or volume shares. | *Windows Server `STORES` Financial Documents* |
| `PROTECTS` | `firewall` | `subnet`, `server`, `storage` | Security perimeter guarding a target network segment or host. | *pfSense `PROTECTS` 192.168.1.0/24* |
| `STORES_CUI` | `storage`, `cloud_service`, `data_asset` | `data_asset` | Direct reference to Controlled Unclassified Information. | *AWS Volume `STORES_CUI` Client CUI Files* |

---

## 3. Node & Edge Security Attributes

Each node and edge contains security metadata evaluated by the GraphRAG compliance engine:

### Node Security Flags
* **`stores_cui`** (`bool`): `True` if the asset stores or transmits Controlled Unclassified Information (CUI).
* **`has_firewall_or_mfa`** (`bool`): `True` if endpoint protection, MFA, or firewall controls are confirmed.
* **`ip_or_subnet`** (`str`): Explicit CIDR subnet (e.g. `192.168.2.0/24`) or IP address.
* **`os_or_system`** (`str`): Operating system or appliance firmware (e.g. `Windows 11`, `TrueNAS SCALE`).

### Edge Security Flags
* **`is_encrypted`** (`bool`): `True` if traffic in transit is encrypted (e.g., OpenVPN, TLS 1.3, IPSec).

---

## 4. Clarification Card Generation Rules

When natural language prompts leave security properties ambiguous, the topology parser generates **Interactive Clarification Cards** for 1-click user confirmation:

1. **Unconfirmed CUI Encryption**: If a storage node or data asset is flagged as storing CUI, but volume encryption (e.g., BitLocker, AES-256) is unmentioned.
2. **Ambiguous VPN / MFA Controls**: If remote users log in over VPN, but Multi-Factor Authentication (MFA) enforcement is unconfirmed.
3. **Unspecified IP Subnets**: If endpoints are described without an IP range, assigning default `192.168.1.0/24` with a prompt asking the user to confirm their local subnet.
