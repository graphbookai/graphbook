import { SerializationError } from '../graph';
import React, { Space, Typography } from 'antd';
const { Text } = Typography;

export function SerializationErrorMessages({ errors }: { errors: SerializationError[] }) {
    return (
        <Space direction="vertical">
            {errors.map((error, i) => (
                <div key={i}>
                    <Text>{error.type} on node </Text>
                    <Text strong>{error.node}</Text>
                    {error.pin && <span><Text>, at pin </Text><Text strong>{error.pin}</Text></span>}
                </div>
            ))}
        </Space>
    );
}
