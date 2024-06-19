import React, { useCallback, useState } from 'react';
import { Flex } from 'antd';
import { NodeResizer, Handle, Position } from 'reactflow';
import { Node } from 'reactflow';
const handleStyle = {
    borderRadius: '50%',
    position: 'relative',
    top: '0%',
    right: 0,
    left: 0,
    transform: 'translate(0,0)',
};
const innerHandleStyle = {
    ...handleStyle,
    backgroundColor: '#fff',
    border: '2px dashed #4f4f4f',
}
const inHandleStyle = {
    ...handleStyle,
    marginRight: '5px',
};
const inInnerHandleStyle = {
    ...innerHandleStyle,
    marginLeft: '5px',
};
const outHandleStyle = {
    ...handleStyle,
    marginLeft: '5px'
};
const outInnerHandleStyle = {
    ...innerHandleStyle,
    marginRight: '5px',
};
export function Group({ data, width, height }) {
    const { label } = data;
    const style = {
        backgroundColor: '#f0f0f080',
    };
    const { inputs, outputs } = data.exports;
    const stepInputs = Object.entries(inputs)
                        .filter(([_, v]) => v.type === 'step')
                        .map(([name, v]) => ({ name, ...v }));
    const stepOutputs = Object.entries(outputs)
                        .filter(([_, v]) => v.type === 'step')
                        .map(([name, v]) => ({ name, ...v }));
    const resourceInputs = Object.entries(inputs)
                        .filter(([_, v]) => v.type === 'resource')
                        .map(([name, v]) => ({ name, ...v }));
    const resourceOutputs = Object.entries(outputs)
                        .filter(([_, v]) => v.type === 'resource')
                        .map(([name, v]) => ({ name, ...v }));


    return (
        <div className='workflow-node group'>
            <NodeResizer minWidth={200} minHeight={200}/>
            <Flex gap="small" justify='space-between'>
                <div style={{marginLeft: '5px'}}>{label}</div>
            </Flex>
            <Flex vertical={true} className="handles">
                <div className="inputs">
                    {
                        stepInputs.map((input, i) => {
                            return (
                                <div key={i} className="input" style={{backgroundColor: '#fff', borderRadius: '10%', padding: '2px 5px', margin: '1px 0'}}>
                                    <Handle style={inHandleStyle} type="target" position={Position.Left} id={input.name} />
                                    <span className="label">{input.name}</span>
                                    <Handle style={inInnerHandleStyle} type="source" position={Position.Right} id={input.name+"_inner"} />
                                </div>
                            );
                        })
                    }
                    {
                        resourceInputs.map((input, i) => {
                            return (
                                <div key={i} className="input" style={{backgroundColor: '#fff', borderRadius: '10%', padding: '2px 5px', margin: '1px 0'}}>
                                    <Handle
                                        className="parameter"
                                        style={inHandleStyle}
                                        type="target"
                                        position={Position.Left}
                                        id={input.name}
                                    />
                                    <span className="label">{input.name}</span>
                                    <Handle style={inInnerHandleStyle} type="source" position={Position.Right} id={input.name+"_inner"} />
                                </div>
                            );
                        })
                    }
                </div>
                <div className='outputs'>
                    {
                        stepOutputs.map((output, i) => {
                            return (
                                <div key={i} className="output" style={{backgroundColor: '#fff', borderRadius: '10%', padding: '2px 5px', margin: '1px 0'}}>
                                    <Handle style={outInnerHandleStyle} type="target" position={Position.Left} id={output.name+"_inner"} />
                                    <span className="label">{output.name}</span>
                                    <Handle style={outHandleStyle} type="source" position={Position.Right} id={output.name} />
                                </div>
                            );
                        })
                    }
                    {
                        resourceOutputs.map((output, i) => {
                            return (
                                <div key={i} className="output" style={{backgroundColor: '#fff', borderRadius: '10%', padding: '2px 5px', margin: '1px 0'}}>
                                    <Handle style={outInnerHandleStyle} type="target" position={Position.Left} id={output.name+"_inner"} />
                                    <span className="label">{output.name}</span>
                                    <Handle className="parameter" style={outHandleStyle} type="source" position={Position.Right} id={output.name} />
                                </div>
                            );
                        })
                    }
                </div>
            </Flex>
        </div>
    );
}


export function groupIfPossible(changedNodes: Node[], allNodes: Node[]) {
    const groupNodes = allNodes.filter((node) => node.type === 'group');
    const changedNodesIds = changedNodes.map(({ id }) => id);
    return allNodes.map((node) => {
        if (node.type === 'group' || !changedNodesIds.includes(node.id)) {
            return node;
        }

        const { position, width, height } = node;
        if (!width || !height) {
            return node;
        }

        for(const groupNode of groupNodes) {
            const gpos = groupNode.position;
            const w = groupNode.width;
            const h = groupNode.height;
            if (!w || !h) {
                continue;
            }
            const groupBounds = [gpos.x, gpos.y, gpos.x + w, gpos.y + h];

            if(node.parentId === groupNode.id) {
                if (!(position.x > 0 &&
                    position.y > 0 &&
                    position.x + width < w &&
                    position.y + height < h)
                ) {
                    node.parentId = '';
                    node.position = { x: position.x + gpos.x, y: position.y + gpos.y };
                }
            } else {
                if (position.x > groupBounds[0] &&
                    position.y > groupBounds[1] &&
                    position.x + width < groupBounds[2] &&
                    position.y + height < groupBounds[3]
                ) {
                    node.parentId = groupNode.id;
                    node.position = { x: position.x - gpos.x, y: position.y - gpos.y };
                }
            }
        }

        return node;
    });
}

export function getExportedHandle(node: Node, handleId: string, isTarget: boolean) {
    if (isTarget) {
        if (isInternalHandle(handleId)) {
            return getExportedOutputHandle(node, handleId);
        } else {
            return getExportedInputHandle(node, handleId);
        }
    } else  {
        if (isInternalHandle(handleId)) {
            return getExportedInputHandle(node, handleId);
        } else {
            return getExportedOutputHandle(node, handleId);
        }
    }
}


export function getExportedInputHandle(node: Node, handleId: string) {
    const toReturn = {};
    if (handleId.endsWith('_inner')) {
        handleId = handleId.slice(0, -6);
        toReturn['inner'] = true;
    }
    return { ...toReturn, ...node.data.exports.inputs[handleId] };
}

export function getExportedOutputHandle(node: Node, handleId: string) {
    const toReturn = {};
    if (handleId.endsWith('_inner')) {
        handleId = handleId.slice(0, -6);
        toReturn['inner'] = true;
    }
    return { ...toReturn, ...node.data.exports.outputs[handleId] };
}

export function isInternalHandle(handleId: string) {
    return handleId.endsWith('_inner');
}
