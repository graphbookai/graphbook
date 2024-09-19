import React, { useCallback, useMemo, useState, useEffect } from 'react';
import { Typography, Flex, Button } from 'antd';
import { usePluginWidgets } from '../../../hooks/Plugins';
import { NotePreview } from './NotePreview';
import { NumberWidget, StringWidget, BooleanWidget, FunctionWidget, DictWidget, ListWidget } from './Widgets';
import { useAPI } from '../../../hooks/API';
import { usePrompt } from '../../../hooks/Prompts';

const { Text } = Typography;
export type PromptProps = {
    stepId: string,
    note: any,
    msg: string,
    type: string,
    def: any,
    show_images?: boolean,
    options?: any,
};

const getWidgetLookup = (pluginWidgets) => {
    const lookup = {
        number: NumberWidget,
        string: StringWidget,
        boolean: BooleanWidget,
        bool: BooleanWidget,
        function: FunctionWidget,
        dict: DictWidget,
    };
    pluginWidgets.forEach((widget) => {
        lookup[widget.type] = widget.children;
    });
    return lookup;
};

function Widget({ type, options, value, onChange }) {
    const pluginWidgets = usePluginWidgets();
    const widgets = useMemo(() => {
        return getWidgetLookup(pluginWidgets);
    }, [pluginWidgets]);

    if (type.startsWith('list')) {
        return <ListWidget name="Answer" def={[]} onChange={onChange} type={type} />
    }

    if (widgets[type]) {
        return widgets[type]({ name: "Answer", def: value, onChange, style: options.style });
    }
}


export function Prompt({ nodeId }: { nodeId: string }) {
    const API = useAPI();
    const [prompt, setSubmitted] = usePrompt(nodeId);
    const [value, setValue] = useState(null);
    const [loading, setLoading] = useState(false);
    const onChange = useCallback((value) => {
        setValue(value);
    }, []);

    const onSubmit = useCallback(async () => {
        if (API) {
            setLoading(true);
            const res = await API.respondToPrompt(nodeId, value);
            console.log(res);
            setLoading(false);
            setSubmitted();
        }
    }, [value, API, nodeId]);

    if (!prompt || prompt.type === null) {
        return null;
    }

    return (
        <Flex className="prompt" vertical>
            <Text>Prompted:</Text>
            <NotePreview data={prompt.note} showImages={prompt.showImages || false}/>
            <Text>{prompt.msg}</Text>
            <Widget type={prompt.type} options={prompt.options} value={value} onChange={onChange} />
            <Button loading={loading} className="prompt" type="primary" size="small" onClick={onSubmit}>Submit</Button>
        </Flex>
    );
}
