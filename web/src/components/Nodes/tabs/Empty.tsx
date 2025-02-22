import React from 'react';
import { Empty } from 'antd';

export type EmptyTabProps = {
    description?: string;
};

export function EmptyTab({ description }: EmptyTabProps) {
    return (
        <Empty
            style={{ fontSize: 8 }}
            imageStyle={{ height: 40 }}
            description={description}
        />
    );
}
