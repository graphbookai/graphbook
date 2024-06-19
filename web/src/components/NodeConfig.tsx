import React, { useCallback, useState, useMemo } from 'react';
import { useReactFlow } from 'reactflow';
import type { Node } from 'reactflow';
import { Collapse, Typography, Card, Flex, Descriptions, theme, Input, Button } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { DescriptionsProps } from 'antd';
import { keyRecursively } from '../utils';
const { Text } = Typography;

export function NodeConfig() {
    const { getNodes, setNodes, setEdges } = useReactFlow();
    const { token } = theme.useToken();
    const nodes = getNodes();

    const items = useMemo(() => {
        return nodes.filter(node => node.selected).map(node => {
            let nodeView;
            if( node.type === 'step' ) {
                nodeView = <StepView node={node} />;
            }
            if(node.type === 'resource') {
                nodeView = <ResourceView node={node} />;
            }
            if(node.type === 'group') {
                nodeView = <GroupView node={node} setNodes={setNodes} setEdges={setEdges} />;
            }
            return {
                key: node.id,
                label: node.data.label,
                children: nodeView
            };
        });
    }, [nodes]);

    if (items.length === 0) {
        return null;
    }
    return (
        <div style={{ background: token.colorBgContainer, borderRadius: token.borderRadius, minWidth: '350px' }}>
            <Text style={{margin: token.margin}}>Node Properties</Text>
            <Collapse defaultActiveKey={items[0]?.key} bordered={false} items={items}/>
        </div>
    );
}

function StepView({ node }) {
    const items: DescriptionsProps['items'] = [
        {
            label: 'ID',
            children: node.id
        },
        {
            label: 'Category',
            children: node.data.category
        },
        {
            label: 'Inputs',
            children: node.data.inputs.join(', '),
            span: 2
        },
        {
            label: 'Parameters',
            children: Object.entries(node.data.parameters).map(([name, parameter]) => (
                <Card>
                    <Text>{name}</Text>
                    <pre>{JSON.stringify(parameter, null, 2)}</pre>
                </Card>
            )),
            span: 2
        },
        {
            label: 'Outputs',
            children: node.data.outputs.join(', ')
        }
    ];
    return (
        <Descriptions bordered={true} column={2} items={items} />
    );
}

function ResourceView({ node }) {
    const items: DescriptionsProps['items'] = [
        {
            label: 'ID',
            children: node.id
        },
        {
            label: 'Category',
            children: node.data.category
        },
        {
            label: 'Parameters',
            children: Object.entries(node.data.parameters).map(([name, parameter]) => (
                <Card>
                    <Text>{name}</Text>
                    <pre>{JSON.stringify(parameter, null, 2)}</pre>
                </Card>
            )),
            span: 2
        }
    ];
    return (
        <Descriptions bordered={true} column={2} items={items} />
    );
}

type GroupNode = {
    id: string,
    data: {
        label: string,
        exports: {
            inputs: Record<string, { type: string }>,
            outputs: Record<string, { type: string }>
        }
    }
}

const onChangeInputExportName = (oldName: string, newName: string, node: GroupNode, setNodes, setEdges) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { inputs } = n.data.exports;
                const input = inputs[oldName];
                delete inputs[oldName];
                inputs[newName] = input;
                return {
                    ...n,
                    data: {
                        ...n.data,
                        exports: {
                            ...n.data.exports,
                            inputs
                        }
                    }
                };
            }
            return n;
        });
        return updatedNodes;
    });
    setEdges((edges) => {
        const updatedEdges = edges.map(e => {
            if (e.target === node.id) {
                if (e.targetHandle === oldName) {
                    e.targetHandle = newName;
                }
            }
            if (e.source === node.id) {
                if (e.sourceHandle === oldName + '_inner') {
                    e.sourceHandle = newName + '_inner';
                }
            }
            return e;
        });
        return updatedEdges;
    });
}

const onChangeOutputExportName = (oldName: string, newName: string, node: GroupNode, setNodes, setEdges) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { outputs } = n.data.exports;
                const output = outputs[oldName];
                delete outputs[oldName];
                outputs[newName] = output;
            }
            return n;
        });
        return updatedNodes;
    });
    setEdges((edges) => {
        const updatedEdges = edges.map(e => {
            if (e.target === node.id) {
                if (e.targetHandle === oldName + '_inner') {
                    e.targetHandle = newName + '_inner';
                }
            }
            if (e.source === node.id) {
                if (e.sourceHandle === oldName) {
                    e.sourceHandle = newName;
                }
            }
            return e;
        });
        return updatedEdges;
    });
}

const onDeleteInputExport = (name: string, node: GroupNode, setNodes, setEdges) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { inputs } = n.data.exports;
                delete inputs[name];
                return {
                    ...n,
                    data: {
                        ...n.data,
                        exports: {
                            ...n.data.exports,
                            inputs
                        }
                    }
                };
            }
            return n;
        });
        return updatedNodes;
    });
    setEdges((edges) => {
        const updatedEdges = edges.filter(e => {
            if (e.target === node.id) {
                return e.targetHandle !== name;
            }
            if (e.source === node.id) {
                return e.sourceHandle !== name + '_inner';
            }
            return true;
        });
        return updatedEdges;
    });
}

const onDeleteOutputExport = (name: string, node: GroupNode, setNodes, setEdges) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { outputs } = n.data.exports;
                delete outputs[name];
                return {
                    ...n,
                    data: {
                        ...n.data,
                        exports: {
                            ...n.data.exports,
                            outputs
                        }
                    }
                };
            }
            return n;
        });
        return updatedNodes;
    });
    setEdges((edges) => {
        const updatedEdges = edges.filter(e => {
            if (e.source === node.id) {
                return e.sourceHandle !== name;
            }
            if (e.target === node.id) {
                return e.targetHandle !== name + '_inner';
            }
            return true;
        });
        return updatedEdges;
    });
}

function GroupView(props: { node: GroupNode, setNodes: any, setEdges: any}) {
    const { node } = props;
    const onChangeInput = useCallback((oldName, newName) => {
        onChangeInputExportName(oldName, newName, node, props.setNodes, props.setEdges)
    }, [node]);
    const onChangeOutput = useCallback((oldName, newName) => {
        onChangeOutputExportName(oldName, newName, node, props.setNodes, props.setEdges)
    }, [node]);
    const onDeleteInput = useCallback((name) => {
        onDeleteInputExport(name, node, props.setNodes, props.setEdges)
    }, [node]);
    const onDeleteOutput = useCallback((name) => {
        onDeleteOutputExport(name, node, props.setNodes, props.setEdges)
    }, [node]);

    const items: DescriptionsProps['items'] = keyRecursively([
        {
            label: 'ID',
            children: node.id
        },
        {
            label: 'Name',
            children: (
                <Input defaultValue={node.data.label} onChange={(e) => props.setNodes((nodes) => {
                    return nodes.map(n => {
                        if (n.id === node.id) {
                            return {
                                ...n,
                                data: {
                                    ...n.data,
                                    label: e.target.value
                                }
                            };
                        }
                        return n;
                    });
                })}/>
            )
        },
        {
            label: 'Step Inputs',
            children: Object.entries(node.data.exports.inputs)
                .filter(([_, input]) => input.type === "step")
                .map(([name, input]) => (
                    <Flex key={name}>
                        <Input defaultValue={name} onChange={(e) => onChangeInput(name, e.target.value)}/>
                        <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteInput(name)}></Button>
                    </Flex>
                )),
        },
        {
            label: 'Resource Inputs',
            children: Object.entries(node.data.exports.inputs)
                .filter(([_, input]) => input.type === "resource")
                .map(([name, input]) => (
                    <Flex key={name}>
                        <Input defaultValue={name} onChange={(e) => onChangeInput(name, e.target.value)}/>
                        <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteInput(name)}></Button>
                    </Flex>
                )),
        },
        {
            label: 'Step Outputs',
            children: Object.entries(node.data.exports.outputs)
                .filter(([_, output]) => output.type === "step")
                .map(([name, output]) => (
                    <Flex key={name}>
                        <Input defaultValue={name} onChange={(e) => onChangeOutput(name, e.target.value)}/>
                        <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteOutput(name)}></Button>
                    </Flex>
                )),
        },
        {
            label: 'Resource Outputs',
            children: Object.entries(node.data.exports.outputs)
                .filter(([_, output]) => output.type === "resource")
                .map(([name, output]) => (
                    <Flex key={name}>
                        <Input defaultValue={name} onChange={(e) => onChangeOutput(name, e.target.value)}/>
                        <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteOutput(name)}></Button>
                    </Flex>
                )),
        }
    ], "");
    return (
        <Descriptions bordered={true} column={1} items={items} />
    );
}