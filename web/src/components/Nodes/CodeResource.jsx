import { useCallback, useState } from 'react';
import { Handle, Position, useReactFlow } from 'reactflow';
import { Card, theme } from 'antd';
import { Graph } from '../../graph';
const { useToken } = theme;

const handleStyle = { 
  backgroundColor: '#22A7F0',
  border: '1px solid #22A7F0',
  borderRadius: '50%',
  position: 'relative',
  top: '0%',
  right: 0,
  left: 0,
  transform: 'translate(0,0)',
};

const parameterHandleStyle = {
  ...handleStyle,
  backgroundColor: '#22F210',
  borderRadius: '50%',
  marginLeft: '5px'
};
 
export function CodeResource({ id, data }) {
  const [targetHandle, setTargetHandle] = useState(null);
  const reactFlowInstance = useReactFlow();
  const { token } = useToken();

  const onHandleConnect = useCallback((connection) => {
    setTargetHandle(connection.targetHandle);
  });

  const onTextChange = useCallback((e) => {
    reactFlowInstance.setNodes((nodes)=> {
      return Graph.editNodeData(id, {value: e.target.value}, nodes);
    });
  });

  return (
    <Card className="workflow-node" style={{backgroundColor: token.colorInfoBg}}>
      <div className="title">Code</div>
      { targetHandle ? <FnHeader fn={targetHandle}/> : ""}
      <textarea className="code" onChange={onTextChange} defaultValue={data.value}></textarea>
      <div className="handles">
        <div className="inputs"></div>
        <div className='outputs'>
          <div className="output">
            <span className="label">Fn</span>
            <Handle style={parameterHandleStyle} type="source" position={Position.Right} id="fn" onConnect={onHandleConnect}/>
          </div>
        </div>
      </div>
    </Card>
  );
}

function FnHeader({fn}) {
  const headers = {
    "split_item_fn": "def split_item_fn(item: any):",
    "split_fn": "def split_fn(note: Note):",
  }
  return (
    <div className="fn-header">
      <div className="fn-name">{headers[fn]}</div>
    </div>
  );

}
