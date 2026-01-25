import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';  // Add this import
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Panel,
  Handle,
  Position
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

// Update your node components to accept onClick handler
const SignerNode = ({ data }) => (
  <div 
    style={{ 
      padding: '8px', 
      borderRadius: '5px', 
      background: '#C4F1F9', 
      border: '1px solid #4299E1',
      textAlign: 'center',
      width: '180px',
      cursor: 'pointer'  // Add cursor pointer
    }}
    onClick={() => data.onClick && data.onClick('signer', data.id)}  // Add click handler
  >
    <Handle
      type="target"
      position={Position.Top}
      style={{ background: '#555' }}
    />
    <div style={{ fontWeight: 'bold', fontSize: '12px' }}>{data.name}</div>
    <div style={{ fontSize: '10px', color: '#666' }}>{data.title}</div>
  </div>
);

const UnitNode = ({ data }) => (
  <div 
    style={{ 
      padding: '8px', 
      borderRadius: '5px', 
      background: 'var(--primary-blue)', 
      color: 'white',
      border: '1px solid var(--primary-blue)',
      textAlign: 'center',
      width: '200px',
      cursor: 'pointer'  // Add cursor pointer
    }}
    onClick={() => data.onClick && data.onClick('unit', data.id)}  // Add click handler
  >
    <Handle
      type="target"
      position={Position.Top}
      style={{ background: '#555' }}
    />
    <div style={{ fontWeight: 'bold', fontSize: '13px' }}>{data.name}</div>
    <div style={{ fontSize: '11px' }}>{data.title}</div>
    <Handle
      type="source"
      position={Position.Bottom}
      style={{ background: '#555' }}
    />
  </div>
);

// Update the node styles to use CSS variables
const OrgNode = ({ data }) => (
  <div 
    style={{ 
      padding: '10px', 
      borderRadius: '5px', 
      background: 'var(--secondary-blue)', 
      color: 'white',
      border: '1px solid var(--secondary-blue)',
      textAlign: 'center',
      width: '220px',
      cursor: 'pointer'
    }}
    onClick={() => data.onClick && data.onClick('organization', data.id)}
  >
    <div style={{ fontWeight: 'bold', fontSize: '14px' }}>{data.name}</div>
    <div style={{ fontSize: '12px' }}>{data.title}</div>
    <Handle
      type="source"
      position={Position.Bottom}
      style={{ background: '#555' }}
    />
  </div>
);

// Define node types
const nodeTypes = {
  organization: OrgNode,
  unit: UnitNode,
  signer: SignerNode,
};

// Update your main component
const OrgChartViewer = ({ orgData, onNodeClick }) => {
  const navigate = useNavigate();  // Add this hook
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();
  const [maxDepth, setMaxDepth] = useState(3); 
  const [layout, setLayout] = useState('hierarchical');
  
  // Use ref to track if layout has been applied
  const layoutAppliedRef = useRef(false);
  
  // Default click handler if none provided
  const handleNodeClick = useCallback((entityType, entityId) => {
    if (onNodeClick) {
      onNodeClick(entityType, entityId);
    } else {
      // Default behavior: navigate to entity detail page
      navigate(`/entity/${entityType}/${entityId}`);
    }
  }, [onNodeClick, navigate]);
  
  // Layout configurations
  const layoutConfigs = {
    hierarchical: { 
      rankdir: 'TB',
      align: 'DL',
      ranksep: 120,
      nodesep: 80,
      edgesep: 10,
    },
    force: { 
      rankdir: 'LR',
      ranksep: 150,
      nodesep: 100
    }
  };
  
  // Get current layout config
  const currentLayout = layout === 'force' ? layoutConfigs.force : layoutConfigs.hierarchical;
  
  // Dagre graph layout algorithm
  const getLayoutedElements = useCallback((inputNodes, inputEdges) => {
    if (!inputNodes.length) return { nodes: [], edges: [] };
    
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph(currentLayout);
    
    // Add nodes to dagre with different sizes based on type
    inputNodes.forEach((node) => {
      let width = 180;
      let height = 60;
      
      // Adjust size based on node type
      if (node.type === 'organization') {
        width = 220;
        height = 80;
      } else if (node.type === 'unit') {
        width = 200;
        height = 70;
      }
      
      dagreGraph.setNode(node.id, { width, height });
    });
    
    // Add edges to dagre
    inputEdges.forEach((edge) => {
      dagreGraph.setEdge(edge.source, edge.target);
    });
    
    // Calculate positions
    dagre.layout(dagreGraph);
    
    // Get positions from dagre
    const layoutedNodes = inputNodes.map((node) => {
      const nodeWithPosition = dagreGraph.node(node.id);
      
      // Center the node based on its width and height
      const xOffset = node.type === 'organization' ? 110 : 
                      node.type === 'unit' ? 100 : 90;
      const yOffset = node.type === 'organization' ? 40 : 
                      node.type === 'unit' ? 35 : 30;
      
      return {
        ...node,
        position: {
          x: nodeWithPosition.x - xOffset, 
          y: nodeWithPosition.y - yOffset
        }
      };
    });
    
    return { nodes: layoutedNodes, edges: inputEdges };
  }, [currentLayout]);
  
  // Process the org data into nodes and edges - only depends on orgData and maxDepth
  const processOrgData = useCallback((data) => {
    if (!data) return { nodes: [], edges: [] };
    
    const nodes = [];
    const edges = [];
    const nodeMap = new Map(); // Track nodes we've created
    
    // First create the organization node
    nodes.push({
      id: data.id,
      data: { 
        name: data.name,  // Changed from label to name
        title: data.title,  // Changed from subLabel to title
        id: data.id,  // Pass ID to data
        onClick: handleNodeClick  // Pass click handler
      },
      type: 'organization',
      position: { x: 0, y: 0 },
      style: {
        background: '#2B6CB0',
        color: 'white',
        border: '1px solid #2B6CB0',
        borderRadius: '5px',
        padding: '10px',
        fontSize: '14px',
        fontWeight: 'bold',
        width: 220,
      }
    });
    nodeMap.set(data.id, true);
    
    // Process children based on type (unit or signer)
    if (data.children && data.children.length > 0) {
      // First process units to ensure they appear first
      const units = data.children.filter(child => child.title === 'Unit');
      const signers = data.children.filter(child => child.title === 'Signer' || child.className === 'signer-node');
      
      // Process all units
      units.forEach(unit => {
        // Add unit node if not already added
        if (!nodeMap.has(unit.id)) {
          nodes.push({
            id: unit.id,
            data: { 
              name: unit.name,  // Changed from label to name
              title: unit.title,  // Changed from subLabel to title
              id: unit.id,  // Pass ID to data
              onClick: handleNodeClick  // Pass click handler
            },
            type: 'unit',
            position: { x: 0, y: 0 },
            style: {
              background: '#4299E1',
              color: 'white',
              border: '1px solid #4299E1',
              borderRadius: '5px',
              padding: '8px',
              fontSize: '13px',
              fontWeight: 'bold',
              width: 200,
            }
          });
          nodeMap.set(unit.id, true);
          
          // Connect unit to organization
          edges.push({
            id: `org-${data.id}-to-unit-${unit.id}`,
            source: data.id,
            target: unit.id,
            type: 'smoothstep',
            animated: false,
            style: { stroke: '#4299E1', strokeWidth: 2 }
          });
          
          // Process unit's children (signers or sub-units)
          if (unit.children && unit.children.length > 0) {
            unit.children.forEach((child, index) => {
              if (!nodeMap.has(child.id)) {
                // Determine if child is a signer or unit
                const isSubUnit = child.title === 'Unit';
                
                nodes.push({
                  id: child.id,
                  data: { 
                    name: child.name,  // Changed from label to name
                    title: child.title,  // Changed from subLabel to title
                    id: child.id,  // Pass ID to data
                    onClick: handleNodeClick  // Pass click handler
                  },
                  type: isSubUnit ? 'unit' : 'signer',
                  position: { x: 0, y: 0 },
                  style: {
                    background: isSubUnit ? '#4299E1' : '#C4F1F9',
                    color: isSubUnit ? 'white' : 'black',
                    border: `1px solid ${isSubUnit ? '#4299E1' : '#C4F1F9'}`,
                    borderRadius: '5px',
                    padding: '6px',
                    fontSize: '12px',
                    width: 180,
                  }
                });
                nodeMap.set(child.id, true);
                
                // Create edge with unique ID
                edges.push({
                  id: `unit-${unit.id}-to-${isSubUnit ? 'unit' : 'signer'}-${child.id}`,
                  source: unit.id,
                  target: child.id,
                  type: 'smoothstep',
                  animated: false,
                  style: { 
                    stroke: isSubUnit ? '#4299E1' : '#C4F1F9', 
                    strokeWidth: 2 
                  }
                });
              }
            });
          }
        }
      });
      
      // Then process direct signers
      signers.forEach(signer => {
        if (!nodeMap.has(signer.id)) {
          nodes.push({
            id: signer.id,
            data: { 
              name: signer.name,  // Changed from label to name
              title: signer.title,  // Changed from subLabel to title
              id: signer.id,  // Pass ID to data
              onClick: handleNodeClick  // Pass click handler
            },
            type: 'signer',
            position: { x: 0, y: 0 },
            style: {
              background: '#C4F1F9',
              color: 'black',
              border: '1px solid #C4F1F9',
              borderRadius: '5px',
              padding: '6px',
              fontSize: '12px',
              width: 180,
            }
          });
          nodeMap.set(signer.id, true);
          
          // Create edge with unique ID
          edges.push({
            id: `org-${data.id}-to-signer-${signer.id}`,
            source: data.id,
            target: signer.id,
            type: 'smoothstep',
            animated: false,
            style: { stroke: '#C4F1F9', strokeWidth: 2 }
          });
        }
      });
    }
    
    // Validate edges - ensure all source/target nodes exist
    const validEdges = edges.filter(edge => {
      const sourceExists = nodeMap.has(edge.source);
      const targetExists = nodeMap.has(edge.target);
      if (!sourceExists || !targetExists) {
        console.warn(`Invalid edge: ${edge.id}, source exists: ${sourceExists}, target exists: ${targetExists}`);
      }
      return sourceExists && targetExists;
    });
    
    console.log(`Created ${nodes.length} nodes and ${validEdges.length} valid edges`);
    
    return { nodes, edges: validEdges };
  }, [maxDepth, handleNodeClick]);  // Add handleNodeClick to dependencies
  
  // Use memoized values for processed data - only recalculate when orgData or processing function changes
  const { nodes: processedNodes, edges: processedEdges } = useMemo(
    () => processOrgData(orgData),
    [orgData, processOrgData]
  );

  // Handle layout changes separately from data processing
  useEffect(() => {
    layoutAppliedRef.current = false;
  }, [layout, maxDepth]); // Reset layout applied flag when these change
  
  // Apply layout in an effect, but only once per data/layout change
  useEffect(() => {
    if (processedNodes.length > 0 && !layoutAppliedRef.current) {
      layoutAppliedRef.current = true;
      
      const { nodes: layoutedNodes, edges: layoutedEdges } = 
        getLayoutedElements(processedNodes, processedEdges);
      
      // Debug logging to see what we're working with
      console.log('Setting nodes:', layoutedNodes.map(n => ({ id: n.id, type: n.type })));
      console.log('Setting edges:', layoutedEdges.map(e => ({ id: e.id, source: e.source, target: e.target })));
      
      // Set nodes first, then edges after a brief delay to ensure nodes are rendered
      setNodes(layoutedNodes);
      
      // Small delay to ensure nodes are set before edges
      setTimeout(() => {
        setEdges(layoutedEdges);
        
        // Fit view after everything is rendered
        setTimeout(() => {
          if (fitView) fitView({ padding: 0.2 });
        }, 100);
      }, 50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    processedNodes, 
    processedEdges
  ]);
  
  // Render the flow diagram
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
        minZoom={0.15}
        maxZoom={1.5}
        nodesDraggable={true}
        elementsSelectable={true}
        defaultEdgeOptions={{
          type: 'smoothstep',
          style: {
            stroke: '#555',
            strokeWidth: 2,
          },
          markerEnd: {
            type: 'arrowclosed',
          },
        }}
      >
        <Controls />
        <MiniMap 
          nodeStrokeColor={(node) => node.style?.background || '#eee'}
          nodeColor={(node) => node.style?.background || '#fff'}
          maskColor="rgba(0, 0, 0, 0.1)"
        />
        <Background variant="dots" gap={12} size={1} />
        
        <Panel position="top-right">
          <div style={{ 
  position: 'absolute', 
  top: '10px', 
  left: '10px', 
  zIndex: 1000, 
  backgroundColor: 'var(--card-bg)', 
  padding: '10px', 
  borderRadius: '5px',
  border: '1px solid var(--border-color)',
  boxShadow: '0 2px 4px var(--shadow)'
}}>
            <h3 style={{ margin: '0 0 10px 0' }}>Layout Options</h3>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button 
                onClick={() => setLayout('hierarchical')}
                style={{ 
                  padding: '5px 10px', 
                  background: layout === 'hierarchical' ? '#4299E1' : '#f1f1f1',
                  color: layout === 'hierarchical' ? 'white' : 'black',
                  border: '1px solid #ddd',
                  cursor: 'pointer',
                  borderRadius: '3px'
                }}
              >
                Hierarchical
              </button>
              <button 
                onClick={() => setLayout('force')}
                style={{ 
                  padding: '5px 10px', 
                  background: layout === 'force' ? '#4299E1' : '#f1f1f1',
                  color: layout === 'force' ? 'white' : 'black',
                  border: '1px solid #ddd',
                  cursor: 'pointer',
                  borderRadius: '3px'
                }}
              >
                Horizontal
              </button>
            </div>
            <div style={{ marginTop: '10px' }}>
              <label style={{ display: 'block', marginBottom: '5px' }}>Max Levels:</label>
              <select 
                value={maxDepth} 
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                style={{ padding: '5px', width: '100%' }}
              >
                <option value={1}>1 Level</option>
                <option value={2}>2 Levels</option>
                <option value={3}>3 Levels</option>
                <option value={4}>4 Levels</option>
                <option value={999}>All Levels</option>
              </select>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export default OrgChartViewer;