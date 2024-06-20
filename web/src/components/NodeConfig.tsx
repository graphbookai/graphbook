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
            <Collapse bordered={false} items={items}/>
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
                <Card key={name}>
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
                <Card key={name}>
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
            inputs: Array<{ name: string, type: string }>,
            outputs: Array<{ name: string, type: string }>,
        }
    }
}

const onChangeInputExportName = (index: number, newName: string, node: GroupNode, setNodes) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { inputs } = n.data.exports;
                inputs[index].name = newName;
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
}

const onChangeOutputExportName = (index: number, newName: string, node: GroupNode, setNodes) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { outputs } = n.data.exports;
                outputs[index].name = newName;
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
}

const onDeleteInputExport = (index: number, node: GroupNode, setNodes, setEdges) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { inputs } = n.data.exports;
                inputs.splice(index, 1);
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
                return e.targetHandle !== index;
            }
            if (e.source === node.id) {
                return e.sourceHandle !== index + '_inner';
            }
            return true;
        });
        return updatedEdges;
    });
}

const onDeleteOutputExport = (index: number, node: GroupNode, setNodes, setEdges) => {
    setNodes((nodes) => {
        const updatedNodes = nodes.map(n => {
            if (n.id === node.id) {
                const { outputs } = n.data.exports;
                outputs.splice(index, 1);
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
                return e.sourceHandle !== index;
            }
            if (e.target === node.id) {
                return e.targetHandle !== index + '_inner';
            }
            return true;
        });
        return updatedEdges;
    });
}

function GroupView(props: { node: GroupNode, setNodes: any, setEdges: any}) {
    const { node } = props;
    const onChangeInput = useCallback((index, newName) => {
        onChangeInputExportName(index, newName, node, props.setNodes)
    }, [node]);
    const onChangeOutput = useCallback((index, newName) => {
        onChangeOutputExportName(index, newName, node, props.setNodes)
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
                <Input defaultValue={node.data.label} onChange={(e) => {
                    props.setNodes((nodes) => {
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
                    });
                }}/>
            )
        },
        {
            label: 'Step Inputs',
            children: node.data.exports.inputs
                .filter(input => input.type === "step")
                .map((input, i) => (
                    <Flex key={i}>
                        <Input defaultValue={input.name} onChange={(e) => onChangeInput(i, e.target.value)}/>
                        <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteInput(i)}></Button>
                    </Flex>
                )),
        },
        {
            label: 'Resource Inputs',
            children: node.data.exports.inputs
                .filter(input => input.type === "resource")
                .map((input, i) => (
                        <Flex key={i}>
                            <Input defaultValue={input.name} onChange={(e) => onChangeInput(i, e.target.value)}/>
                            <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteInput(i)}></Button>
                        </Flex>
                    )),
        },
        {
            label: 'Step Outputs',
            children: node.data.exports.outputs
                .filter(output => output.type === "step")
                .map((output, i) => (
                        <Flex key={i}>
                            <Input defaultValue={output.name} onChange={(e) => onChangeOutput(i, e.target.value)}/>
                            <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteOutput(i)}></Button>
                        </Flex>
                    )),
        },
        {
            label: 'Resource Outputs',
            children: node.data.exports.outputs
                .filter(output => output.type === "resource")
                .map((output, i) => (
                        <Flex key={i}>
                            <Input defaultValue={output.name} onChange={(e) => onChangeOutput(i, e.target.value)}/>
                            <Button danger icon={<DeleteOutlined/>} onClick={() => onDeleteOutput(i)}></Button>
                        </Flex>
                    )),
        }
    ], "");
    return (
        <Descriptions bordered={true} column={1} items={items} />
    );
}