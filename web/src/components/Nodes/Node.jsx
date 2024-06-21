import { useCallback, useEffect, useState } from 'react';
import { Handle, Position, useNodes, useEdges } from 'reactflow';
import { Card, Collapse, Badge, Flex, Button, Image, Descriptions, theme } from 'antd';
import { SearchOutlined, ProfileOutlined, CaretRightOutlined } from '@ant-design/icons';
import { Widget } from './Widgets';
import { API } from '../../api';
import { Graph } from '../../graph';
import { useRunState } from '../../hooks/RunState';
import { mediaUrl, keyRecursively } from '../../utils';
const { Panel } = Collapse;
const { useToken } = theme;
import './node.css';

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
    marginRight: '5px'
};
const parameterHandleStyle = {
    ...inHandleStyle,
    borderRadius: '50%',
};
const outHandleStyle = {
    ...handleStyle,
    marginLeft: '5px'
};

const createViewEventListener = (id, callback) => {
    return (msg) => {
        msg = JSON.parse(msg.data);
        if (msg.type !== "view") {
            return;
        }
        const { data } = msg;
        if (!data[id]) {
            return;
        }

        callback(data[id]);
    }
};

const createStatsEventListener = (id, callback) => {
    return (msg) => {
        msg = JSON.parse(msg.data);
        if (msg.type !== "stats") {
            return;
        }
        const { data } = msg;
        if (!data[id]) {
            return;
        }

        callback(data[id]);
    }
};

const createLogsEventListener = (id, callback) => {
    return (msg) => {
        msg = JSON.parse(msg.data);
        if (msg.type !== "logs") {
            return;
        }
        const { data } = msg;
        if (!data[id]) {
            return;
        }

        callback(data[id]);
    }
};

const isWidgetType = (type) => {
    return ['number', 'string', 'boolean'].includes(type);
};

export function WorkflowStep({ id, data, selected, ...props }) {
    const { name, parameters, inputs, outputs } = data;
    const [quickViewData, setQuickViewData] = useState(null);
    const [logsData, setLogsData] = useState([]);
    const [recordCount, setRecordCount] = useState(0);
    const [errored, setErrored] = useState(false);
    const nodes = useNodes();
    const edges = useEdges();
    const { token } = useToken();

    const appendNewLogsCallback = useCallback((newEntries) => {
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
    }, [logsData]);

    useEffect(() => {
        const viewListener = createViewEventListener(id, data => {
            setQuickViewData(data);
        });
        const statsListener = createStatsEventListener(id, data => {
            setRecordCount(data.queue_size)
        });
        const logsListener = createLogsEventListener(id, appendNewLogsCallback);
        API.addWsEventListener('message', viewListener);
        API.addWsEventListener('message', statsListener);
        API.addWsEventListener('message', logsListener);
        return () => {
            API.removeWsEventListener('message', viewListener);
            API.removeWsEventListener('message', statsListener);
            API.removeWsEventListener('message', logsListener);
        };
    }, []);

    useEffect(() => {
        for (const log of logsData) {
            if (log.type === 'error') {
                setErrored(true);
                return;
            }
        }

        setErrored(false);
    }, [logsData]);

    const [runState, runStateShouldChange] = useRunState();
    const run = useCallback(() => {
        const [graph, resources] = Graph.serializeForAPI(nodes, edges);
        API.run(graph, resources, id);
        runStateShouldChange();
    }, [nodes, edges]);

    const selectedStyle = {
        border: `1px dashed ${token.colorInfoActive}`,
        padding: '1px',
        transform: 'translate(-2px, -2px)',
        borderRadius: token.borderRadius
    };

    const erroredStyle = {
        border: `1px solid ${token.colorError}`,
        padding: '1px',
        transform: 'translate(-2px, -2px)',
        borderRadius: token.borderRadius
    };

    return (
        <div style={errored ? erroredStyle : (selected ? selectedStyle : {})}>
            <Badge count={recordCount} color={token.colorFill} style={{ color: token.colorText }} overflowCount={Infinity}>
                <Card className="workflow-node">
                    <Flex gap="small" justify='space-between' className='title'>
                        <div>{name}</div>
                        <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'stopped'}/>
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
                    { !data.isCollapsed && <Monitor quickViewData={quickViewData} logsData={logsData} />}
                </Card>
            </Badge>
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

                    const { items } = value;
                    const descriptionItems = keyRecursively(Object.entries(items).filter(([_, itemList]) => {
                        return itemList.filter(item => item.type?.slice(0, 5) === 'image').length > 0;
                    }).map(([itemKey, itemList]) => {
                        const images = itemList.filter(item => item.type?.slice(0, 5) === 'image');
                        return {
                            label: itemKey,
                            children: (
                                <Flex key={i} vertical>
                                    {
                                        images.map((item, i) => (
                                            <Image key={i} src={mediaUrl(item.item)} width={100} />
                                        ))
                                    }
                                </Flex>
                            )
                        };
                    }), "none");
                    return (
                        <Panel className='content' header={key} key={i}>
                            <Flex style={{ overflowY: 'scroll', maxHeight: '300px' }}>
                                <div style={{ marginRight: '5px' }}>
                                    {JSON.stringify(value, null, 2)}
                                </div>
                                {
                                    descriptionItems.length > 0 && <Descriptions layout="vertical" bordered items={descriptionItems} />
                                }
                            </Flex>
                        </Panel>
                    );
                })
            }
        </Collapse>
    );
}
