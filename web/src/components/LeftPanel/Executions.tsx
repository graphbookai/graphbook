import { Typography, theme, Badge, Space, Empty, Flex } from "antd";
import { RightOutlined, DownOutlined } from "@ant-design/icons";
import React, { useState, useMemo, useCallback, MouseEventHandler } from "react";
import { Resizable } from "re-resizable";
import { useAPIEveryGraphLastValue } from "../../hooks/API";
const { useToken } = theme;
const { Text } = Typography;

type RunState = "initializing" | "running" | "errored" | "finished";
type AntdBadgeStatus = "default" | "processing" | "success" | "error" | "warning";

const runStateToStatus: Record<RunState, AntdBadgeStatus> = {
    "initializing": "warning",
    "running": "processing",
    "errored": "error",
    "finished": "success",
};

type ExecutionData = {
    name: string;
    status: RunState;
};

export default function Executions({ isExecution, isWorkflowSet }: { isExecution: Function, isWorkflowSet: boolean }) {
    const [isOpened, setIsOpened] = useState(true);
    const [isResizing, setIsResizing] = useState(false);
    const [selectedExecution, setSelectedExecution] = useState<string>();
    const { token } = useToken();
    const runStates = useAPIEveryGraphLastValue("run_state");

    const onExecutionClick = useCallback((name: string) => {
        if (isExecution(name)) {
            setSelectedExecution(name);
        } else {
            setSelectedExecution(undefined);
        }
    }, [isExecution]);

    const executions: ExecutionData[] = useMemo(() => {
        if (!runStates) {
            return [];
        }
        return Object.entries<RunState>(runStates).map(([name, status]) => {
            return {
                name,
                status,
            };
        });
    }, [runStates]);

    const handleStyle: React.CSSProperties = useMemo(() => {
        return {
            backgroundColor: isResizing ? token.colorInfoHover : token.colorBorder,
            height: 3 + (isResizing ? 2 : 0),
            top: -3 - (isResizing ? 2 : 0),
        };
    }, [token, isResizing]);

    const headerStyle: React.CSSProperties = useMemo(() => {
        return {
            cursor: 'pointer',
            marginTop: 'auto',
            position: 'relative',
            borderTop: `2px solid ${token.colorBorder}`,
        };
    }, [token]);

    if (!isOpened) {
        return (
            <div style={headerStyle}>
                <Flex style={{ paddingTop: 5 }} onClick={() => setIsOpened(true)}>
                    <RightOutlined style={{ marginRight: 5 }} />
                    <Text strong>Executions</Text>
                </Flex>
            </div>

        );
    }

    return (
        <Resizable
            maxHeight={'70%'}
            minHeight={100}
            style={{ position: 'relative', marginTop: 'auto', paddingTop: 5 }}
            defaultSize={{ height: 100 }}
            enable={{ top: true }}
            handleStyles={{ top: handleStyle }}
            onResizeStart={() => setIsResizing(true)}
            onResizeStop={() => setIsResizing(false)}
        >
            <Flex style={{ cursor: 'pointer', marginBottom: 5, marginTop: 2 }} onClick={() => setIsOpened(false)}>
                <DownOutlined style={{ marginRight: 5 }} />
                <Text strong>Executions</Text>
            </Flex>
            {
                executions.length === 0 ?
                    <Empty description="No executions found" /> :
                    <Flex vertical style={{ overflowY: 'auto', height: '100%', width: '100%' }}>
                        {
                            executions.map((execution, index) => {
                                return (
                                    <ExecutionEntry
                                        key={index}
                                        name={execution.name}
                                        status={execution.status}
                                        selected={!isWorkflowSet && execution.name === selectedExecution}
                                        onClick={() => onExecutionClick(execution.name)}
                                    />
                                );
                            })
                        }
                    </Flex>
            }
        </Resizable>
    );
}


function ExecutionEntry({ name, status, selected, onClick }: { name: string, status: RunState, selected: boolean, onClick: MouseEventHandler }) {
    const [isHovered, setIsHovered] = useState(false);
    const { token } = useToken();

    const handleMouseEnter = useCallback(() => {
        setIsHovered(true);
    }, []);

    const handleMouseLeave = useCallback(() => {
        setIsHovered(false);
    }, []);

    const style = useMemo(() => {
        return {
            borderRadius: token.borderRadius,
            backgroundColor: selected ? token.colorInfoText : isHovered ? token.colorBgTextHover : token.colorBgContainer,
            cursor: 'pointer',
            padding: '2px 5px',
            margin: '2px 0',
        }
    }, [selected, isHovered, token]);

    return (
        <Space direction="horizontal" align="start" style={style} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave} onClick={onClick}>
            <Badge status={runStateToStatus[status]} />
            <Text>{name}</Text>
        </Space>
    );
}
