import React, { useCallback, useEffect, useState } from 'react';
import { Flex, Card, Typography, theme } from 'antd';
import { NodeResizer, Handle, Position, useUpdateNodeInternals } from 'reactflow';
import { Node } from 'reactflow';
const { Text } = Typography;

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
export function Group({ id, data }) {
    const { label } = data;
    const updateNodeInternals = useUpdateNodeInternals();


    useEffect(() => {
        updateNodeInternals(id);
    }, [id, data.exports]);

    if (data.isCollapsed) {
        return <CollapsedGroup data={data} />;
    }

    return (
        <div className='workflow-node group'>
            <NodeResizer minWidth={150} minHeight={150}/>
            <Flex className='title' justify='space-between' style={{margin: '0 2px'}}>
                <Text>{label}</Text>
            </Flex>
            <GroupPins data={data} />
        </div>
    );
}

function CollapsedGroup({ data }) {
    const { label } = data;
    return (
        <Card className='workflow-node group collapsed'>
            <Flex className='title' justify='space-between' style={{margin: '0 2px'}}>
                <Text>{label}</Text>
            </Flex>
            <GroupPins data={data} />
        </Card>
    );
}

const sortPinFn = (a, b) => {
    if (a.type === b.type) {
        return Number(a.id) - Number(b.id);
    }
    return a.type === 'step' ? -1 : 1;
}

function GroupPins({ data }) {
    const { inputs, outputs } = data.exports;
    const { token } = theme.useToken();
    const c = data.isCollapsed;
    const handleContainerStyle = c ? {} : {
        backgroundColor: token.colorBgBase,
        borderRadius: '10%',
        padding: '2px 5px',
        margin: '1px 0'
    };

    return (
        <Flex vertical={true} className="handles">
            <div className="inputs">
                {
                    inputs
                        .map((input, i)=>({...input, id: i}))
                        .sort(sortPinFn)
                        .map((input, i) => {
                            return (
                                <div key={i} className="input" style={handleContainerStyle}>
                                    <Handle style={inHandleStyle} type="target" position={Position.Left} id={String(input.id)} className={input.type === 'resource' ? 'parameter' : ''}/>
                                    <Text style={{alignSelf: 'left'}} className="label">{input.name}</Text>
                                    {!c && <Handle style={inInnerHandleStyle} type="source" position={Position.Right} id={`${input.id}_inner`} />}
                                </div>
                            );
                    })
                }
            </div>
            <div className='outputs'>
                {
                    outputs
                        .map((output, i)=>({...output, id: i}))
                        .sort(sortPinFn)
                        .map((output, i) => {
                            return (
                                <div key={i} className="output" style={handleContainerStyle}>
                                    {!c && <Handle style={outInnerHandleStyle} type="target" position={Position.Left} id={`${output.id}_inner`} />}
                                    <Text className="label">{output.name}</Text>
                                    <Handle style={outHandleStyle} type="source" position={Position.Right} id={String(output.id)} className={output.type === 'resource' ? 'parameter' : ''}/>
                                </div>
                            );
                        })
                }
            </div>
        </Flex>
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
