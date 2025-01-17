import { Typography, theme, Badge, Space, Empty, Flex } from "antd";
import React, { useState, useMemo, useCallback, MouseEventHandler } from "react";
import { Resizable } from "re-resizable";
import { useAPIAnyGraphLastValue} from "../../hooks/API";
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

export default function Executions({ setExecution }: { setExecution: Function }) {
    const [isResizing, setIsResizing] = useState(false);
    const [selectedExecution, setSelectedExecution] = useState<string>();
    const { token } = useToken();
    const runStates = useAPIAnyGraphLastValue("run_state");

    const onExecutionClick = useCallback((name: string) => {
        setSelectedExecution(name);
        setExecution(name);
    }, [setExecution]);

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
    }, [runStates])

    const handleStyle = useMemo(() => {
        return {
            backgroundColor: isResizing ? token.colorInfoHover : token.colorBorder,
            height: 2 + (isResizing ? 2 : 0),
        };
    }, [token, isResizing]);


    return (
        <Resizable
            maxHeight={'70%'}
            style={{ position: 'relative', marginTop: 'auto' }}
            defaultSize={{ height: 300 }}
            enable={{ top: true }}
            handleStyles={{ top: handleStyle }}
            onResizeStart={() => setIsResizing(true)}
            onResizeStop={() => setIsResizing(false)}
        >
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
                                    selected={execution.name === selectedExecution}
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
            backgroundColor: selected ? token.colorInfoBgHover : isHovered ? token.colorBgTextHover : token.colorBgBase,
            cursor: 'pointer',
            padding: 5,
        }
    }, [selected, isHovered]);

    return (
        <Space direction="horizontal" align="start" style={style} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave} onClick={onClick}>
            <Badge status={runStateToStatus[status]} />
            <Text>{name}</Text>
        </Space>
    );
}
