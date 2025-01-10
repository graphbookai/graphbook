import { Typography, theme, Badge, Space, Empty } from "antd";
import React, { useState, useMemo, useCallback, MouseEventHandler } from "react";
import { Resizable } from "re-resizable";
import { useAPIMessage } from "../../hooks/API";
const { useToken } = theme;
const { Text } = Typography;

type ExecutionStatus = "processing" | "default";

type ExecutionData = {
    name: string;
    status: ExecutionStatus;
};

export default function Executions({ setWorkflow, remainingHeight }: { setWorkflow: Function, remainingHeight: number }) {
    const [isResizing, setIsResizing] = useState(false);
    const [executions, setExecutions] = useState<ExecutionData[]>([]);
    const [selectedExecution, setSelectedExecution] = useState<string>();
    const { token } = useToken();


    const onExecutionClick = useCallback((name: string) => {
        setSelectedExecution(name);
        setWorkflow(name);
    }, [setWorkflow]);

    const trySetNewExecution = useCallback((data) => {
        if (!data.filename) {
            return;
        }

        for (let i = 0; i < executions.length; i++) {
            if (executions[i].name === data.filename) {
                executions[i].status = data.status;
                setExecutions(executions);
                return;
            }
        }

        setExecutions([...executions, { name: data.filename, status: data.is_running ? "processing" : "default" }]);
    }, [executions])

    useAPIMessage("run_state", (message) => {
        trySetNewExecution(message);
    });

    const handleStyle = useMemo(() => {
        return {
            backgroundColor: isResizing ? token.colorInfoHover : token.colorBorder,
            height: 2 + (isResizing ? 2 : 0),
        };
    }, [token, isResizing])

    return (
        <Resizable
            maxHeight={remainingHeight}
            style={{ marginTop: 'auto' }}
            defaultSize={{ height: 300 }}
            enable={{ top: true }}
            handleStyles={{ top: handleStyle }}
            onResizeStart={() => setIsResizing(true)}
            onResizeStop={() => setIsResizing(false)}
        >
            {
                executions.length === 0 ?
                <Empty description="No executions found" /> :
                <Space direction="vertical" style={{ overflowY: 'auto', height: '100%', width: '100%' }}>
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
                </Space>
            }
        </Resizable>
    );
}


function ExecutionEntry({ name, status, selected, onClick }: { name: string, status: ExecutionStatus, selected: boolean, onClick: MouseEventHandler }) {
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
            <Badge status={status} />
            <Text>{name}</Text>
        </Space>
    );
}
