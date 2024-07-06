import React from 'react';
import { Typography, Flex } from 'antd';

const { Title, Paragraph } = Typography;


export function WelcomeScreen() {
    return (
        <Flex vertical justify='center' align='center' style={{width: '100%', height: '100%'}}>
            <Title>Welcome to Graphbook</Title>
            <Paragraph>
                Create a new .json file to begin.
            </Paragraph>
            <Paragraph>
                To learn more about how to create workflows and custom nodes visit our documentation at <a target="_blank" rel="noopener noreferrer" href="https://docs.graphbook.ai">docs.graphbook.ai</a>
            </Paragraph>
        </Flex>
    );
};
