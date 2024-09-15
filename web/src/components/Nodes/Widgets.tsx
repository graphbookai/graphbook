import { Switch, Typography, theme, Flex, Button } from 'antd';
import { PlusOutlined, MinusCircleOutlined, MinusOutlined } from '@ant-design/icons';
import React, { useCallback, useState, useMemo } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { basicDark } from '@uiw/codemirror-theme-basic';
import { bbedit } from '@uiw/codemirror-theme-bbedit';
import { Graph } from '../../graph';
import { useReactFlow } from 'reactflow';
import { usePluginWidgets } from '../../hooks/Plugins';
const { Text } = Typography;
const { useToken } = theme;

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

export function Widget({ id, type, name, value }) {
    const { setNodes } = useReactFlow();
    const pluginWidgets = usePluginWidgets();
    const widgets = useMemo(() => {
        return getWidgetLookup(pluginWidgets);
    }, [pluginWidgets]);

    const onChange = useCallback((value) => {
        setNodes(nodes => {
            return Graph.editParamData(id, name, { value }, nodes);
        });
    }, []);

    if (type.startsWith('list')) {
        return <ListWidget name={name} def={value} onChange={onChange} type={type} />
    }

    if (widgets[type]) {
        return widgets[type]({ name, def: value, onChange });
    }
}

export function NumberWidget({ name, def, onChange }) {
    return (
        <InputNumber onChange={onChange} label={name} value={def} />
    );
}

export function StringWidget({ name, def, onChange }) {
    return (
        <Input onChange={onChange} label={name} value={def} />
    );
}

export function BooleanWidget({ name, def, onChange }) {
    return (
        <Flex justify='space-between' align="center" className="input-container">
            <Text>{name}</Text>
            <Switch size="small" defaultChecked={def} onChange={onChange} />
        </Flex>
    )
}

export function FunctionWidget({ name, def, onChange }) {
    const token = useToken();

    return (
        <CodeMirror
            value={def}
            theme={token.theme.id == 0 ? bbedit : basicDark}
            height='100%'
            width='100%'
            minWidth='300px'
            extensions={[python()]}
            onChange={onChange}
        />
    );
}

const listElementDefaultValues = {
    "string": "",
    "number": 0,
    "boolean": false,
    "function": "",
};

export function ListWidget({ name, def, onChange, type }) {
    const { token } = useToken();
    const subType = useMemo(() => type.split('[')[1].split(']')[0], [type]);
    const pluginWidgets = usePluginWidgets();
    const widgets = useMemo(() => {
        return getWidgetLookup(pluginWidgets);
    }, [pluginWidgets]);

    const Widget = useMemo(() => {
        return widgets[subType];
    }, [subType]);

    const onAddItem = useCallback(() => {
        const value = listElementDefaultValues[subType];
        if (!def) {
            onChange([value]);
            return;
        }
        onChange([...def, value]);
    }, [def]);

    const onRemoveItem = useCallback((index) => {
        const newDef = [...def];
        newDef.splice(index, 1);
        onChange(newDef);
    }, [def]);

    if (!Widget) {
        return (
            <div className="input-container">
                <Text type="danger">(Invalid widget type: {subType})</Text>
            </div>
        );
    }

    return (
        <Flex className="input-container" style={{ border: `1px solid ${token.colorBorder}` }}>
            <Text style={{margin: "2px 1px"}}>{name}</Text>
            <Flex vertical style={{ marginLeft: '4px' }}>
                {def && def.map((item, i) => {
                    return (
                        <Flex style={{ margin: '1px 0' }} key={i}>
                            <Widget def={item} onChange={(value) => {
                                const newDef = [...def];
                                newDef[i] = value;
                                onChange(newDef);
                            }} />
                            <Button tabIndex={-1} style={{ marginLeft: 1 }} size="small" icon={<MinusOutlined />} onClick={() => onRemoveItem(i)} />
                        </Flex>
                    )
                })}
                <Flex justify='end'>
                    <Button size={"small"} icon={<PlusOutlined />} onClick={onAddItem} />
                </Flex>
            </Flex>
        </Flex>
    )
}

export function DictWidget({ name, def, onChange, type }) {
    const { token } = useToken();
    const value = useMemo(() => {
        if (!def) {
            return [];
        }

        if (Array.isArray(def)) {
            return def;
        }

        try {
            return Object.entries(def).map(([key, value]) => {
                let type = typeof value as string;
                if (type === 'number') {
                    type = 'float';
                }
                return [type, key, value];
            });
        } catch (e) {
            return [];
        }
    }, [def]);

    const onAddItem = useCallback(() => {
        if (!value) {
            onChange([['string', '', '']]);
            return;
        }
        onChange([...value, ['string', '', '']]);
    }, [value]);

    const onRemoveItem = useCallback((index) => {
        const newValue = [...value];
        newValue.splice(index, 1);
        onChange(newValue);
    }, [value]);

    const onTypeChange = useCallback((index, type) => {
        const newValue = [...value];
        newValue[index][0] = type;
        onChange(newValue);
    }, [value]);

    const onKeyChange = useCallback((index, key) => {
        const newValue = [...value];
        newValue[index][1] = key;
        onChange(newValue);
    }, [value]);

    const onValueChange = useCallback((index, v) => {
        const newValue = [...value];
        newValue[index][2] = v;
        onChange(newValue);
    }, [value]);

    const selectedInputs = useMemo(() => {
        return value.map((item, i) => {
            if (item[0] === 'string') {
                return <Input onChange={(value) => onValueChange(i, value)} value={item[2]} />
            }
            if (item[0] === 'float' || item[0] === 'int' || item[0] === 'number') {
                return <InputNumber onChange={(value) => onValueChange(i, value)} value={item[2]} />
            }
            if (item[0] === 'boolean') {
                return <Switch size="small" defaultChecked={def} onChange={(value) => onValueChange(i, value)} value={item[2]} />
            }
        });
    }, [value]);

    const options = useMemo(() => {
        const options = ['string', 'float', 'int', 'boolean'];
        return options.map((option) => ({
            label: option,
            value: option,
        }));
    }, []);
    
    return (
        <Flex className="input-container" style={{ border: `1px solid ${token.colorBorder}` }}>
            <Text style={{margin: "2px 1px"}}>{name}</Text>
            <Flex vertical style={{ marginLeft: '4px' }}>
                {value && value.map((item, i) => {
                    return (
                        <Flex justify='space-between' style={{margin: '1px 0' }} key={i}>
                            <Flex>
                                <Select
                                    value={item[0]}
                                    onChange={(value) => onTypeChange(i, value)}
                                    options={options}
                                />
                                <Input onChange={(value) => onKeyChange(i, value)} value={item[1]} />
                            </Flex>
                            
                            <Flex>
                                {
                                    selectedInputs[i]
                                }
                                <Button tabIndex={-1} style={{ marginLeft: 1 }} size="small" icon={<MinusOutlined />} onClick={() => onRemoveItem(i)} />
                            </Flex>
                        </Flex>
                    )
                })}
                <Flex justify='end'>
                    <Button size={"small"} icon={<PlusOutlined />} onClick={onAddItem} />
                </Flex>
            </Flex>
        </Flex>
    )
}

function Select({ onChange, options, value }) {
    const { token } = useToken();

    const inputStyle = {
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
    };



    const onValueChange = useCallback((e) => {
        onChange(e.target.value);
    }, []);

    return (
        <div className="input-container">
            <select className="input" onChange={onValueChange} value={value} style={inputStyle}>
                {
                    options.map((option, i) => {
                        return <option key={i} value={option.value}>{option.label}</option>
                    })
                }
            </select>
        </div>
    )
}

function InputNumber({ onChange, label, value }: { onChange: (value: number) => void, label?: string, value?: number }) {
    const { token } = useToken();
    const defaultFocusedStyle = { border: `1px solid ${token.colorBorder}` };
    const [focusedStyle, setFocusedStyle] = useState(defaultFocusedStyle);

    const inputStyle = {
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
    };
    const labelStyle = {
        backgroundColor: token.colorBgContainer
    }
    const handleChange = (e) => {
        onChange(Number(e.target.value));
    };
    const onInputFocus = useCallback((isFocused) => {
        if (isFocused) {
            setFocusedStyle({ border: `1px solid ${token.colorInfoActive}` });
        } else {
            setFocusedStyle(defaultFocusedStyle);
        }
    }, []);

    return (
        <div style={focusedStyle} className="input-container">
            {label &&
                <Text style={labelStyle}>{label}</Text>
            }
            <input
                onFocus={() => onInputFocus(true)}
                onBlur={() => onInputFocus(false)}
                onChange={handleChange}
                style={inputStyle}
                className="input"
                type="number"
                value={value || 0}
            />
        </div>
    );
}


function Input({ onChange, label, value }: { onChange: (value: string) => void, label?: string, value?: string }) {
    const { token } = useToken();
    const defaultFocusedStyle = { border: `1px solid ${token.colorBorder}` };
    const [focusedStyle, setFocusedStyle] = useState(defaultFocusedStyle)

    const inputStyle = {
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
    };
    const labelStyle = {
        backgroundColor: token.colorBgContainer
    }
    const handleChange = (e) => {
        onChange(e.target.value);
    };

    const onInputFocus = useCallback((isFocused) => {
        if (isFocused) {
            setFocusedStyle({ border: `1px solid ${token.colorInfoActive}` });
        } else {
            setFocusedStyle(defaultFocusedStyle);
        }
    }, []);

    return (
        <div style={focusedStyle} className="input-container">
            {label &&
                <Text style={labelStyle}>{label}</Text>
            }
            <input
                onFocus={() => onInputFocus(true)}
                onBlur={() => onInputFocus(false)}
                onChange={handleChange}
                style={inputStyle}
                className="input"
                type="text"
                value={value || ''}
            />
        </div>
    );
}

export const isWidgetType = (type) => {
    return ['number', 'string', 'boolean', 'bool', 'function'].includes(type) || type.startsWith('list') || type.startsWith('dict');
};
