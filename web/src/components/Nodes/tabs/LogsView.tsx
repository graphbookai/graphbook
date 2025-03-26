import React, { useRef, useEffect, useCallback } from 'react';
import { Flex, Typography, theme } from 'antd';
import { EmptyTab } from './Empty';

const { Text } = Typography;


export function LogsView({ data }) {
    const { token } = theme.useToken();
    const bottomRef = useRef<HTMLDivElement>(null);
    const shouldScrollToBottom = true;

    useEffect(() => {
        if (shouldScrollToBottom) {
            bottomRef.current?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: 'instant' });
        }
    }, [shouldScrollToBottom, data]);

    const bg = useCallback((i) => {
        return i % 2 === 0 ? token.colorBgBase : token.colorBgLayout;
    }, [token]);

    const textOf = useCallback((t) => {
        if (typeof t === 'string') {
            return t;
        }
        return JSON.stringify(t);
    }, []);

    return (
        data.length === 0 ?
            <EmptyTab description='No logs' /> :
            <Flex vertical>
                {
                    data.map((log, i) => {
                        const { msg } = log;
                        const style: React.CSSProperties = {
                            backgroundColor: bg(i),
                            margin: '1px 0',
                            fontSize: '.6em',
                            lineHeight: 1,
                            borderLeft: `2px solid ${token.colorBorder}`,
                            padding: '1px 0 1px 4px'
                        };
                        return (
                            <Text key={log.idx || i} style={style}>{textOf(msg)}</Text>
                        );
                    })
                }
                <div ref={bottomRef} />
            </Flex>
    );
}
