import { useCallback, useEffect, useMemo, useState } from 'react';
import { Handle, Position, useNodes, useEdges, useReactFlow, useOnSelectionChange } from 'reactflow';
import { Card, Collapse, Badge, Flex, Button, theme } from 'antd';
import { SearchOutlined, ProfileOutlined, CaretRightOutlined } from '@ant-design/icons';
import { Widget } from './Widgets';
import { Graph } from '../../graph';
import { useRunState } from '../../hooks/RunState';
import { useAPI, useAPINodeMessage } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { recordCountBadgeStyle } from '../../styles';
const { Panel } = Collapse;
const { useToken } = theme;

const handleStyle = {
    borderRadius: '50%',
    position: 'relative',
    top: '0%',
    right: 0,
    left: 0,
    transform: 'translate(0,0)',
};
const inHandleStyle = {
    ...handleStyle,
    marginRight: '2px'
};
const parameterHandleStyle = {
    ...inHandleStyle,
    borderRadius: '50%',
};
const outHandleStyle = {
    ...handleStyle,
    marginLeft: '2px'
};


const isWidgetType = (type) => {
    return ['number', 'string', 'boolean'].includes(type);
};

export function WorkflowStep({ id, data, selected }) {
    const { name, parameters, inputs, outputs } = data;
    const [quickViewData, setQuickViewData] = useState(null);
    const [logsData, setLogsData] = useState([]);
    const [recordCount, setRecordCount] = useState({});
    const [errored, setErrored] = useState(false);
    const [parentSelected, setParentSelected] = useState(false);
    const [runState, runStateShouldChange] = useRunState();
    const nodes = useNodes();
    const edges = useEdges();
    const { token } = useToken();
    const { getNode } = useReactFlow();

    const API = useAPI();

    const filename = useFilename();
    useAPINodeMessage('stats', id, filename, (msg) => {
        setRecordCount(msg.queue_size || {});
    });
    useAPINodeMessage('view', id, filename, (msg) => {
        setQuickViewData(msg.data);
    });
    useAPINodeMessage('logs', id, filename, useCallback((newEntries) => {
        let wipeIndex = -1;
        for (let i = 0; i < newEntries.length; i++) {
            if (newEntries[i].type === 'wipe') {
                wipeIndex = i;
            }
        }

        if (wipeIndex > -1) {
            newEntries = newEntries.slice(wipeIndex + 1);
        }

        setLogsData([...logsData, ...newEntries]);
    }, [logsData]));

    useEffect(() => {
        for (const log of logsData) {
            if (log.type === 'error') {
                setErrored(true);
                return;
            }
        }

        setErrored(false);
    }, [logsData]);

    const onSelectionChange = useCallback(({ nodes }) => {
        const parentId = getNode(id)?.parentId;
        if (!parentId) {
            return;
        }
        for (const n of nodes) {
            if (parentId === n.id && n.selected) {
                setParentSelected(true);
                return;
            }
        }
        setParentSelected(false);
    }, [id]);

    useOnSelectionChange({
        onChange: onSelectionChange
    });

    const run = useCallback(async () => {
        if (!API) {
            return;
        }
        const [graph, resources] = await Graph.serializeForAPI(nodes, edges);
        API.run(graph, resources, id);
        runStateShouldChange();
    }, [nodes, edges, API]);

    const borderStyle = useMemo(() => {
        const baseStyle = {
            padding: '1px',
            borderRadius: token.borderRadius,
            transform: 'translate(-2px, -2px)'
        };

        const selectedStyle = {
            ...baseStyle,
            border: `1px dashed ${token.colorInfoActive}`
        };

        const erroredStyle = {
            ...baseStyle,
            border: `1px solid ${token.colorError}`,
        };

        const parentSelectedStyle = {
            ...baseStyle,
            border: `1px dashed ${token.colorInfoBorder}`
        };

        if (errored) {
            return erroredStyle;
        }

        if (selected) {
            return selectedStyle;
        }

        if (parentSelected) {
            return parentSelectedStyle;
        }

    }, [token, errored, selected, parentSelected]);

    const badgeIndicatorStyle = useMemo(() => recordCountBadgeStyle(token), [token]);

    return (
        <div style={borderStyle}>
            <Card className="workflow-node">
                <Flex gap="small" justify='space-between' className='title'>
                    <div>{name}</div>
                    <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'stopped' || !API} />
                </Flex>
                <div className="handles">
                    <div className="inputs">
                        {
                            inputs.map((input, i) => {
                                return (
                                    <div key={i} className="input">
                                        <Handle style={inHandleStyle} type="target" position={Position.Left} id="in" />
                                        <span className="label">{input}</span>
                                    </div>
                                );
                            })
                        }
                        {
                            Object.entries(parameters).map(([parameterName, parameter], i) => {
                                if (!isWidgetType(parameter.type)) {
                                    return (
                                        <div key={i} className="input">
                                            <Handle
                                                className="parameter"
                                                style={parameterHandleStyle}
                                                type="target"
                                                position={Position.Left}
                                                id={parameterName}
                                            />
                                            <span className="label">{parameterName}</span>
                                        </div>
                                    );
                                }
                            })
                        }
                    </div>
                    <div className='outputs'>
                        {
                            outputs.map((output, i) => {
                                return (
                                    <div key={i} className="output">
                                        <Badge size="small" styles={{indicator: badgeIndicatorStyle}} count={recordCount[output] || 0} overflowCount={Infinity} />
                                        <span className="label">{output}</span>
                                        <Handle style={outHandleStyle} type="source" position={Position.Right} id={output} />
                                    </div>
                                );
                            })
                        }
                    </div>
                </div>
                <div className='widgets'>
                    {
                        !data.isCollapsed &&
                        Object.entries(parameters).map(([parameterName, parameter], i) => {
                            if (isWidgetType(parameter.type)) {
                                return (
                                    <div style={{ marginBottom: '2px' }} key={i} className="parameter">
                                        <Widget id={id} name={parameterName} {...parameter} />
                                    </div>
                                );
                            }
                            return null;
                        }).filter(x => x)
                    }
                </div>
                {!data.isCollapsed && <Monitor quickViewData={quickViewData} logsData={logsData} />}
            </Card>
        </div>
    );
}

function Monitor({ quickViewData, logsData }) {
    return (
        <Collapse className='quickview' defaultActiveKey={[]} bordered={false} expandIcon={({ panelKey }) => {
            switch (panelKey) {
                case '1':
                    return <SearchOutlined size="small" />;
                case '2':
                    return <ProfileOutlined size="small" />;
                default:
                    return null;
            }
        }}>
            <Panel header="Quickview" key="1">
                {
                    quickViewData ?
                        <QuickviewCollapse data={quickViewData} /> :
                        '(No outputs yet)'
                }
            </Panel>
            <Panel header={"Logs" + (logsData.length > 0 ? `(${logsData.length})` : '')} key="2">
                {
                    logsData.length == 0 ?
                        <p className='content'>(No logs yet) </p> :

                        logsData.map((log, i) => {
                            const { msg } = log;
                            return (
                                <p key={i} className='content'>
                                    {msg}
                                </p>
                            );
                        })

                }
            </Panel>
        </Collapse>
    );
}

function QuickviewCollapse({ data }) {
    return (
        <Collapse className='quickview' defaultActiveKey={[]} bordered={false}>
            {
                Object.entries(data).map(([key, value], i) => {

                    // const { items } = value;
                    // const descriptionItems = keyRecursively(Object.entries(items).filter(([_, itemList]) => {
                    //     return itemList.filter(item => item.type?.slice(0, 5) === 'image').length > 0;
                    // }).map(([itemKey, itemList]) => {
                    //     const images = itemList.filter(item => item.type?.slice(0, 5) === 'image');
                    //     return {
                    //         label: itemKey,
                    //         children: (
                    //             <Flex key={i} vertical>
                    //                 {
                    //                     images.map((item, i) => (
                    //                         <Image key={i} src={mediaUrl(item.item)} width={100} />
                    //                     ))
                    //                 }
                    //             </Flex>
                    //         )
                    //     };
                    // }), "none");
                    return (
                        <Panel className='content' header={key} key={i}>
                            <Flex style={{ overflowY: 'scroll', maxHeight: '300px' }}>
                                <div style={{ marginRight: '5px' }}>
                                    {JSON.stringify(value, null, 2)}
                                </div>
                                {
                                    // descriptionItems.length > 0 && <Descriptions layout="vertical" bordered items={descriptionItems} />
                                }
                            </Flex>
                        </Panel>
                    );
                })
            }
        </Collapse>
    );
}
