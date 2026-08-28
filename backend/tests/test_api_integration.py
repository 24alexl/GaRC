from fastapi.testclient import TestClient
from app.main import app

def test_full_api_workflow():
    client = TestClient(app)

    # 1. Test Available Templates
    r_tpl = client.get('/api/templates')
    assert r_tpl.status_code == 200
    templates = r_tpl.json()
    assert len(templates) >= 4

    # 2. Test Load Template
    r_load = client.post('/api/templates/load/clinic')
    assert r_load.status_code == 200
    clinic_topo = r_load.json()
    assert len(clinic_topo.get('nodes', [])) >= 4
    assert "cytoscape_graph" in clinic_topo

    # 3. Test Parse Topology
    r1 = client.post('/api/engine2/parse-topology', json={
        'text': 'We have 8 Windows 11 PCs on 192.168.1.0/24 connected to a Synology NAS storing payroll CUI and a pfSense firewall.'
    })
    assert r1.status_code == 200
    data1 = r1.json()
    assert len(data1.get('nodes', [])) >= 2
    assert "cytoscape_graph" in data1

    # 4. Test Evaluate 5 Technical Families
    r2 = client.post('/api/audit/evaluate-topology')
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2.get("status") == "completed"
    assert data2.get("total_controls_evaluated") > 0
    assert len(data2.get("family_scorecards", [])) == 5
    assert "top_fixes" in data2
    assert "assessor_checklist" in data2
    assert "evaluated_controls" in data2

    # 5. Test Answer Clarification
    r_clarify = client.post('/api/topology/answer-clarification', json={
        'node_id': 'storage_nas',
        'property_name': 'has_firewall_or_mfa',
        'value': True
    })
    assert r_clarify.status_code == 200

    # 6. Test Explain Single Control Finding
    r3 = client.post('/api/audit/explain-control', json={'control_id': '03.13.01'})
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3.get("control_id") == "03.13.01"
    assert "objectives" in data3
    assert len(data3.get("objectives", [])) > 0

    # 7. Test Export Report
    r_export = client.get('/api/report/export?org_name=TestClinic')
    assert r_export.status_code == 200
    rep = r_export.json()
    assert rep.get("organization_name") == "TestClinic"
    assert len(rep.get("family_scores", [])) == 5

    # 8. Test NIST Scorecard
    r4 = client.get('/api/nist-scorecard')
    assert r4.status_code == 200
    data4 = r4.json()
    assert data4.get("status") == "Assessed"
    assert len(data4.get("family_scores", [])) == 5

    # 9. Test Static Web UI serving
    r5 = client.get('/')
    assert r5.status_code == 200
    assert "GaRC" in r5.text
