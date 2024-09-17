import React, { useCallback, useMemo, useState } from 'react';
import { Typography, Flex, Button } from 'antd';
import { usePluginWidgets } from '../../../hooks/Plugins';
import { NotePreview } from './NotePreview';
import { NumberWidget, StringWidget, BooleanWidget, FunctionWidget, DictWidget, ListWidget } from './Widgets';
import { useAPI } from '../../../hooks/API';

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


export function Prompt({ stepId, note, msg, type, options, def, show_images }: PromptProps) {
    const API = useAPI();
    const [value, setValue] = useState(def);
    const onChange = useCallback((value) => {
        setValue(value);
    }, []);

    const onSubmit = useCallback(() => {
        if (API) {
            API.respondToPrompt(stepId, value);
        }
    }, [value]);

    return (
        <Flex className="prompt" vertical>
            <Text>Prompted:</Text>
            <NotePreview data={note} show_images={show_images || false}/>
            <Text>{msg}</Text>
            <Widget type={type} options={options} value={value} onChange={onChange} />
            <Button className="prompt" type="primary" size="small" onClick={onSubmit}>Submit</Button>
        </Flex>
    );
}