import React from 'react';
import { Typography, Flex } from 'antd';

const { Title, Paragraph } = Typography;


export function NotFoundFlow() {
    return (
        <Flex vertical justify='center' align='center' style={{width: '100%', height: '100%'}}>
            <Title>404 :(</Title>
            <Paragraph>
                Couldn't find that workflow. 
            </Paragraph>
            <Paragraph>
                <a target="_blank" rel="noopener noreferrer" href="https://docs.graphbook.ai">docs.graphbook.ai</a>
            </Paragraph>
        </Flex>
    );
};
