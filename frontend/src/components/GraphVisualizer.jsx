import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';

export default function GraphVisualizer({ graphData, onNodeSelect, highlightControlId }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const elements = [];

    if (graphData?.nodes) {
      graphData.nodes.forEach(n => {
        elements.push({ group: 'nodes', data: n.data });
      });
    }

    if (graphData?.edges) {
      graphData.edges.forEach(e => {
        elements.push({ group: 'edges', data: e.data });
      });
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'background-color': '#1e293b',
            'border-width': 2,
            'border-color': '#06b6d4',
            'color': '#f8fafc',
            'font-size': '11px',
            'font-family': 'Inter, sans-serif',
            'font-weight': 500,
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'text-background-color': '#090d16',
            'text-background-opacity': 0.85,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 36,
            'height': 36,
            'transition-property': 'background-color, border-color, border-width, width, height',
            'transition-duration': '0.3s'
          }
        },
        {
          selector: 'node[type = "query"]',
          style: {
            'background-color': '#047857',
            'border-color': '#34d399',
            'width': 52,
            'height': 52,
            'font-weight': 'bold',
            'color': '#34d399'
          }
        },
        {
          selector: 'node[type = "family"]',
          style: {
            'background-color': '#581c87',
            'border-color': '#c084fc',
            'width': 46,
            'height': 46,
            'color': '#e9d5ff'
          }
        },
        {
          selector: 'node[type = "control"]',
          style: {
            'background-color': '#0369a1',
            'border-color': '#38bdf8',
            'width': 42,
            'height': 42,
            'color': '#bae6fd'
          }
        },
        {
          selector: 'node[type = "objective"]',
          style: {
            'background-color': '#451a03',
            'border-color': '#f59e0b',
            'border-width': 1.5,
            'width': 24,
            'height': 24,
            'font-size': '9.5px',
            'color': '#fef08a'
          }
        },
        {
          selector: 'node[type = "server"]',
          style: {
            'background-color': '#312e81',
            'border-color': '#818cf8',
            'border-width': 2.5,
            'width': 44,
            'height': 44,
            'color': '#e0e7ff'
          }
        },
        {
          selector: 'node[type = "subnet"]',
          style: {
            'background-color': '#0f172a',
            'border-color': '#38bdf8',
            'border-width': 2,
            'width': 42,
            'height': 42,
            'color': '#bae6fd'
          }
        },
        {
          selector: 'node[type = "data_asset"]',
          style: {
            'background-color': '#78350f',
            'border-color': '#fbbf24',
            'border-width': 2,
            'width': 36,
            'height': 36,
            'color': '#fef08a'
          }
        },
        {
          selector: 'node[type = "storage"]',
          style: {
            'background-color': '#9a3412',
            'border-color': '#fb923c',
            'width': 40,
            'height': 40
          }
        },
        {
          selector: 'node[type = "firewall"]',
          style: {
            'background-color': '#9f1239',
            'border-color': '#f43f5e',
            'width': 40,
            'height': 40
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#334155',
            'target-arrow-color': '#38bdf8',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.2,
            'curve-style': 'bezier',
            'label': 'data(label)',
            'color': '#94a3b8',
            'font-size': '9px',
            'font-family': 'Inter, sans-serif',
            'text-background-color': '#090d16',
            'text-background-opacity': 0.9,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate'
          }
        },
        {
          selector: 'node[status = "MET"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#10b981',
            'border-width': 2.5,
            'color': '#a7f3d0'
          }
        },
        {
          selector: 'node[status = "UNMET"]',
          style: {
            'background-color': '#4c0519',
            'border-color': '#f43f5e',
            'border-width': 2.5,
            'color': '#fecdd3'
          }
        },
        {
          selector: 'node[status = "INSUFFICIENT_DATA"]',
          style: {
            'background-color': '#451a03',
            'border-color': '#f59e0b',
            'border-width': 2.5,
            'color': '#fef08a'
          }
        },
        {
          selector: 'node[status = "Good"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#34d399',
            'border-width': 2.5,
            'color': '#a7f3d0'
          }
        },
        {
          selector: 'node[status = "Critical Gap"]',
          style: {
            'background-color': '#4c0519',
            'border-color': '#fb7185',
            'border-width': 2.5,
            'color': '#ffe4e6'
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'background-color': '#d97706',
            'border-color': '#fef08a',
            'border-width': 4,
            'width': 54,
            'height': 54,
            'color': '#fef08a',
            'font-weight': 'bold',
            'z-index': 999
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#f59e0b',
            'target-arrow-color': '#f59e0b',
            'width': 4,
            'z-index': 999
          }
        }
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        padding: 40,
        spacingFactor: 1.8,
        avoidOverlap: true,
        nodeDimensionsIncludeLabels: true,
        roots: 'node[type = "cloud_service"], node[type = "firewall"], node[type = "subnet"]'
      }
    });

    cy.on('tap', 'node', (evt) => {
      if (onNodeSelect) onNodeSelect(evt.target.data());
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [graphData]);

  useEffect(() => {
    if (!cyRef.current || !highlightControlId) return;
    const cy = cyRef.current;

    cy.nodes().removeClass('highlighted');
    cy.edges().removeClass('highlighted');

    const targetId = `Ctrl_${highlightControlId}`;
    const ctrlNode = cy.getElementById(targetId);

    if (ctrlNode && ctrlNode.length > 0) {
      const neighborhood = ctrlNode.closedNeighborhood();
      neighborhood.addClass('highlighted');

      if (onNodeSelect) onNodeSelect(ctrlNode.data());

      cy.animate({
        fit: { eles: neighborhood, padding: 60 },
        duration: 450
      });
    }
  }, [highlightControlId]);

  return (
    <div className="w-full h-full relative rounded-lg overflow-hidden bg-slate-950 border border-slate-800">
      <div ref={containerRef} className="w-full h-full min-h-[360px]" />
      {highlightControlId && (
        <div className="absolute top-3 right-3 bg-amber-950/90 text-amber-300 border border-amber-700 text-xs px-3 py-1.5 rounded-md font-mono animate-pulse">
          🔍 Focused Path: Control {highlightControlId}
        </div>
      )}
    </div>
  );
}
