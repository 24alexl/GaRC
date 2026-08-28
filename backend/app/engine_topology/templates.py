from typing import Dict, Any, List

SMALL_BIZ_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "clinic": {
        "id": "clinic",
        "name": "Small Healthcare / Dental Clinic",
        "badge": "Healthcare / HIPAA",
        "description": "5x Staff PCs on Wi-Fi, 1x Reception PC on Ethernet, pfSense Firewall, Synology NAS with Patient EHR / CUI, Guest Wi-Fi.",
        "nodes": [
            {
                "id": "fw_gateway",
                "name": "pfSense Security Gateway",
                "type": "firewall",
                "os_or_system": "pfSense CE",
                "ip_or_subnet": "192.168.1.1",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "subnet_lan",
                "name": "Wired Clinic LAN (192.168.1.0/24)",
                "type": "subnet",
                "ip_or_subnet": "192.168.1.0/24",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "subnet_wifi",
                "name": "Staff Wi-Fi Network",
                "type": "subnet",
                "ip_or_subnet": "192.168.2.0/24",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "subnet_guest",
                "name": "Patient Guest Wi-Fi",
                "type": "subnet",
                "ip_or_subnet": "192.168.3.0/24",
                "stores_cui": False,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "dev_reception",
                "name": "Reception & Billing PC",
                "type": "device",
                "os_or_system": "Windows 11 Pro",
                "ip_or_subnet": "192.168.1.20",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "dev_staff_pcs",
                "name": "5x Exam Room Laptops (Staff Wi-Fi)",
                "type": "device",
                "os_or_system": "Windows 11",
                "ip_or_subnet": "DHCP Range",
                "stores_cui": False,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "storage_nas",
                "name": "Synology NAS (Patient EHR / CUI)",
                "type": "storage",
                "os_or_system": "Synology DSM",
                "ip_or_subnet": "192.168.1.50",
                "stores_cui": True,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "data_cui",
                "name": "Patient EHR & Medical Records (CUI)",
                "type": "data_asset",
                "stores_cui": True,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            }
        ],
        "edges": [
            {"source": "fw_gateway", "target": "subnet_lan", "relationship": "PROTECTS", "is_encrypted": True, "confidence": 1.0},
            {"source": "fw_gateway", "target": "subnet_wifi", "relationship": "PROTECTS", "is_encrypted": True, "confidence": 1.0},
            {"source": "fw_gateway", "target": "subnet_guest", "relationship": "ROUTES_TO", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_reception", "target": "subnet_lan", "relationship": "CONNECTS_TO", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_staff_pcs", "target": "subnet_wifi", "relationship": "CONNECTS_TO", "is_encrypted": False, "confidence": 1.0},
            {"source": "storage_nas", "target": "subnet_lan", "relationship": "CONNECTS_TO", "is_encrypted": False, "confidence": 1.0},
            {"source": "storage_nas", "target": "data_cui", "relationship": "STORES_CUI", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_reception", "target": "storage_nas", "relationship": "ACCESSES", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_staff_pcs", "target": "storage_nas", "relationship": "ACCESSES", "is_encrypted": False, "confidence": 1.0}
        ],
        "clarification_prompts": [
            {
                "node_id": "storage_nas",
                "question": "Is the Synology NAS volume encrypted at rest with AES-256 (BitLocker / DSM Encryption)?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, Encrypted", "No, Unencrypted"]
            },
            {
                "node_id": "subnet_guest",
                "question": "Is the Patient Guest Wi-Fi isolated from the internal clinic LAN via a dedicated VLAN?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, Isolated VLAN", "No, Shared Subnet"]
            },
            {
                "node_id": "dev_staff_pcs",
                "question": "Do staff laptops enforce Multi-Factor Authentication (MFA) or Endpoint EDR?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, MFA Active", "No MFA"]
            }
        ]
    },
    "law_firm": {
        "id": "law_firm",
        "name": "Local Law / CPA Practice",
        "badge": "Legal / Financial",
        "description": "6x Partner Laptops, Office Firewall, Local File Server with Tax & Client CUI, BitLocker active, Remote VPN gateway.",
        "nodes": [
            {
                "id": "fw_gateway",
                "name": "Fortinet FortiGate Firewall",
                "type": "firewall",
                "os_or_system": "FortiOS",
                "ip_or_subnet": "192.168.10.1",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "subnet_lan",
                "name": "Office Secure LAN (192.168.10.0/24)",
                "type": "subnet",
                "ip_or_subnet": "192.168.10.0/24",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "cloud_vpn",
                "name": "Remote Worker SSL-VPN Gateway",
                "type": "cloud_service",
                "os_or_system": "FortiClient VPN",
                "ip_or_subnet": "192.168.10.254",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "dev_partner_pcs",
                "name": "6x Partner Laptops (BitLocker Active)",
                "type": "device",
                "os_or_system": "Windows 11 Pro",
                "ip_or_subnet": "DHCP Range",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "server_files",
                "name": "Windows Server 2022 (Tax & Contracts)",
                "type": "server",
                "os_or_system": "Windows Server 2022",
                "ip_or_subnet": "192.168.10.100",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "data_cui",
                "name": "Client Tax Returns & Case Files (CUI)",
                "type": "data_asset",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            }
        ],
        "edges": [
            {"source": "fw_gateway", "target": "subnet_lan", "relationship": "PROTECTS", "is_encrypted": True, "confidence": 1.0},
            {"source": "fw_gateway", "target": "cloud_vpn", "relationship": "PROTECTS", "is_encrypted": True, "confidence": 1.0},
            {"source": "dev_partner_pcs", "target": "subnet_lan", "relationship": "CONNECTS_TO", "is_encrypted": True, "confidence": 1.0},
            {"source": "dev_partner_pcs", "target": "cloud_vpn", "relationship": "LOGS_IN_VIA", "is_encrypted": True, "confidence": 1.0},
            {"source": "server_files", "target": "subnet_lan", "relationship": "CONNECTS_TO", "is_encrypted": True, "confidence": 1.0},
            {"source": "server_files", "target": "data_cui", "relationship": "STORES_CUI", "is_encrypted": True, "confidence": 1.0},
            {"source": "dev_partner_pcs", "target": "server_files", "relationship": "ACCESSES", "is_encrypted": True, "confidence": 1.0}
        ],
        "clarification_prompts": [
            {
                "node_id": "cloud_vpn",
                "question": "Is Multi-Factor Authentication (MFA / Authenticator App) enforced on the Remote SSL-VPN?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, MFA Enforced", "No, Password Only"]
            },
            {
                "node_id": "server_files",
                "question": "Are off-site backup copies encrypted in transit and at rest?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, Encrypted Backups", "Unencrypted Backups"]
            }
        ]
    },
    "subcontractor": {
        "id": "subcontractor",
        "name": "Small Manufacturer / Defense Subcontractor",
        "badge": "DoD / CMMC / CUI",
        "description": "8x CAD Workstations, Air-gapped Engineering NAS with DoD CUI, Hardware Firewall, Zero-Trust VPN gateway.",
        "nodes": [
            {
                "id": "fw_gateway",
                "name": "Cisco Meraki MX Security Gateway",
                "type": "firewall",
                "os_or_system": "Meraki OS",
                "ip_or_subnet": "10.0.1.1",
                "stores_cui": False,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "subnet_cad",
                "name": "Engineering CAD Subnet (10.0.1.0/24)",
                "type": "subnet",
                "ip_or_subnet": "10.0.1.0/24",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "subnet_shop",
                "name": "Shop Floor CNC Machines (10.0.2.0/24)",
                "type": "subnet",
                "ip_or_subnet": "10.0.2.0/24",
                "stores_cui": False,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "dev_cad_ws",
                "name": "8x Engineering CAD Workstations",
                "type": "device",
                "os_or_system": "Windows 11 Enterprise",
                "ip_or_subnet": "10.0.1.50-58",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "storage_cui_nas",
                "name": "TrueNAS ZFS Vault (DoD Technical Drawings)",
                "type": "storage",
                "os_or_system": "TrueNAS CORE (ZFS Encrypted)",
                "ip_or_subnet": "10.0.1.10",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "data_cui",
                "name": "DoD Defense Specs & Technical Drawings (CUI)",
                "type": "data_asset",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            }
        ],
        "edges": [
            {"source": "fw_gateway", "target": "subnet_cad", "relationship": "PROTECTS", "is_encrypted": True, "confidence": 1.0},
            {"source": "fw_gateway", "target": "subnet_shop", "relationship": "PROTECTS", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_cad_ws", "target": "subnet_cad", "relationship": "CONNECTS_TO", "is_encrypted": True, "confidence": 1.0},
            {"source": "storage_cui_nas", "target": "subnet_cad", "relationship": "CONNECTS_TO", "is_encrypted": True, "confidence": 1.0},
            {"source": "storage_cui_nas", "target": "data_cui", "relationship": "STORES_CUI", "is_encrypted": True, "confidence": 1.0},
            {"source": "dev_cad_ws", "target": "storage_cui_nas", "relationship": "ACCESSES", "is_encrypted": True, "confidence": 1.0}
        ],
        "clarification_prompts": [
            {
                "node_id": "subnet_shop",
                "question": "Is the Shop Floor CNC network strictly isolated from the Engineering CAD subnet via firewall ACLs?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, Strict ACL Isolation", "No, Flat Routing"]
            },
            {
                "node_id": "dev_cad_ws",
                "question": "Are all CAD workstations configured with smart card / FIDO2 hardware token MFA?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, Hardware MFA Active", "Password Only"]
            }
        ]
    },
    "nonprofit": {
        "id": "nonprofit",
        "name": "Community Non-Profit / Legal Clinic",
        "badge": "Non-Profit / Privacy",
        "description": "4x Staff Laptops, Cloud Microsoft 365 / OneDrive holding Donor & Client CUI, Netgear Router, Guest Wi-Fi.",
        "nodes": [
            {
                "id": "fw_gateway",
                "name": "Netgear Business Router / Gateway",
                "type": "firewall",
                "os_or_system": "Netgear Firmware",
                "ip_or_subnet": "192.168.1.1",
                "stores_cui": False,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "subnet_lan",
                "name": "Office Wi-Fi / LAN (192.168.1.0/24)",
                "type": "subnet",
                "ip_or_subnet": "192.168.1.0/24",
                "stores_cui": False,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "dev_staff_laptops",
                "name": "4x Staff Chromebooks & Laptops",
                "type": "device",
                "os_or_system": "ChromeOS / Windows",
                "ip_or_subnet": "DHCP Range",
                "stores_cui": False,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            },
            {
                "id": "cloud_m365",
                "name": "Microsoft 365 / OneDrive Cloud",
                "type": "cloud_service",
                "os_or_system": "Microsoft Cloud",
                "ip_or_subnet": "cloud.microsoft.com",
                "stores_cui": True,
                "has_firewall_or_mfa": True,
                "confidence": 1.0
            },
            {
                "id": "data_cui",
                "name": "Donor Records & Client Intake CUI",
                "type": "data_asset",
                "stores_cui": True,
                "has_firewall_or_mfa": False,
                "confidence": 1.0
            }
        ],
        "edges": [
            {"source": "fw_gateway", "target": "subnet_lan", "relationship": "ROUTES_TO", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_staff_laptops", "target": "subnet_lan", "relationship": "CONNECTS_TO", "is_encrypted": False, "confidence": 1.0},
            {"source": "dev_staff_laptops", "target": "cloud_m365", "relationship": "ACCESSES", "is_encrypted": True, "confidence": 1.0},
            {"source": "cloud_m365", "target": "data_cui", "relationship": "STORES_CUI", "is_encrypted": True, "confidence": 1.0}
        ],
        "clarification_prompts": [
            {
                "node_id": "cloud_m365",
                "question": "Is Microsoft 365 MFA enforced for all staff logins?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, MFA Enforced", "No, Passwords Only"]
            },
            {
                "node_id": "fw_gateway",
                "question": "Is the Netgear router firewall configured with stateful packet inspection and default-deny inbound rules?",
                "property_in_question": "has_firewall_or_mfa",
                "suggested_options": ["Yes, Default-Deny Active", "Default Consumer Settings"]
            }
        ]
    }
}
