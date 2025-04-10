import React from 'react';
import { Flex, Typography } from 'antd';
const { Text, Link } = Typography;;


type ErrorBoundaryProps = {
    children: React.ReactNode;
    fallback?: React.ComponentType<{ error: any }>;
    horizontal?: boolean;
};

type ErrorBoundaryState = {
    hasError: boolean;
    currentError: any;
};

export default class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    isHorizontal: boolean;

    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.isHorizontal = props.horizontal || false;
        this.state = {
            hasError: false,
            currentError: null,
        };
    }

    static getDerivedStateFromError(error: any) {
        return {
            hasError: true,
            currentError: String(error),
        };
    }

    componentDidCatch(error: any, errorInfo: any) {
        console.error("ErrorBoundary caught an error", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                const Component = this.props.fallback;
                return <Component error={this.state.currentError} />;
            }

            return (
                <Flex vertical={!this.isHorizontal} gap={5} justify='center' align='center' style={{ width: '100%', height: '100%' }}>
                    <Text type="danger">Error 😓</Text>
                    <Text>{typeof (this.state.currentError) === 'object' ? JSON.stringify(this.state.currentError) : this.state.currentError}</Text>
                    <Link href="https://github.com/graphbookai/graphbook/issues" target="_blank">Report an issue</Link>
                </Flex>
            );
        }

        return this.props.children;
    }
}
