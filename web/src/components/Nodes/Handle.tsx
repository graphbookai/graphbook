import React, { useMemo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, Typography, Badge, theme } from 'antd';
import { inputHandleStyle, outputHandleStyle, recordCountBadgeStyle } from '../../styles';
import { RemovableTooltip } from '../Tooltip';
const { Text } = Typography;
const { useToken } = theme;

export interface InputHandleProps {
    id: string;
    name: string;
    isResource?: boolean;
    tooltip?: string;
}

export interface OutputHandleProps extends InputHandleProps {
    count: number;
}

export function InputHandle({ id, name, isResource, tooltip }: InputHandleProps) {
    return (
        <div className="input">
            <Handle style={{...inputHandleStyle(), opacity: '0%'}} type="target" position={Position.Left} id={id} className={isResource ? 'parameter' : ''}/>
            <RemovableTooltip title={tooltip}>
                <Text style={{alignSelf: 'left'}} className="label">{name}</Text>
            </RemovableTooltip>
        </div>
    );
}

export function OutputHandle({ id, name, isResource, count }: OutputHandleProps) {
    const { token } = useToken();
    const badgeIndicatorStyle = useMemo(() => recordCountBadgeStyle(token), [token]);

    return (
        <div className="output">
            <Badge size="small" styles={{indicator: badgeIndicatorStyle}} count={count || 0} overflowCount={Infinity} />
            <Text style={{alignSelf: 'right'}} className="label">{name}</Text>
            <Handle style={outputHandleStyle()} type="source" position={Position.Right} id={id} className={isResource ? 'parameter' : ''}/>
        </div>
    );
}
