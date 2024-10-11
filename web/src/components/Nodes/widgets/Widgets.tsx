import { Switch, Typography, theme, Flex, Button, Radio, Select as ASelect } from 'antd';
import { PlusOutlined, MinusOutlined } from '@ant-design/icons';
import React, { useCallback, useState, useMemo, useEffect } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { basicDark } from '@uiw/codemirror-theme-basic';
import { bbedit } from '@uiw/codemirror-theme-bbedit';
import { Graph } from '../../../graph';
import { useReactFlow } from 'reactflow';
import { usePluginWidgets } from '../../../hooks/Plugins';
const { Text } = Typography;
const { useToken } = theme;

export const getWidgetLookup = (pluginWidgets) => {
    const lookup = {
        number: NumberWidget,
        string: StringWidget,
        boolean: BooleanWidget,
        bool: BooleanWidget,
        function: FunctionWidget,
        dict: DictWidget,
        selection: SelectionWidget,
    };

    pluginWidgets.forEach((widget) => {
        lookup[widget.type] = widget.children;
    });
    return lookup;
};

export function Widget({ id, type, name, value, ...props }) {
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
        return widgets[type]({ name, def: value, onChange, ...props });
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

export function BooleanWidget({ name, def, onChange, style }) {
    const input = useMemo(() => {
        if (style === "yes/no") {
            const M = {
                "Yes": true,
                "No": false,
            };
            const M_ = {
                true: "Yes",
                false: "No",
            };
            return <Radio.Group options={["Yes", "No"]} onChange={(e) => onChange(M[e.target.value])} value={M_[def]} optionType="button" />
        }
        return <Switch size="small" defaultChecked={def} onChange={onChange} />
    }, [style, def]);
    return (
        <Flex className="input-container" justify='space-between' align="center">
            <Text>{name}</Text>
            {input}
        </Flex>
    );
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
            <Text style={{ margin: "2px 1px" }}>{name}</Text>
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
    );
}

export function DictWidget({ name, def, onChange }) {
    const { token } = useToken();
    const value = useMemo(() => {
        if (Array.isArray(def)) {
            return def;
        }

        // Needs to be converted to an array of 3-tuples

        if (!def) {
            onChange([]);
            return [];
        }

        try {
            const newValue = Object.entries(def).map(([key, value]) => {
                let type = typeof value as string;
                if (type === 'number') {
                    type = 'float';
                }
                return [type, key, value];
            });
            onChange(newValue);
            return newValue;
        } catch (e) {
            onChange([]);
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
                return <Input placeholder="value" onChange={(value) => onValueChange(i, value)} value={item[2]} />
            }
            if (item[0] === 'float' || item[0] === 'int' || item[0] === 'number') {
                return <InputNumber placeholder="32" onChange={(value) => onValueChange(i, value)} value={item[2]} />
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
        <Flex className="input-container" style={{ border: `1px solid ${token.colorBorder}`, padding: '0 1px 1px 1px' }}>
            <Text style={{ margin: "2px 1px" }}>{name}</Text>
            <Flex vertical style={{ marginLeft: '4px' }}>
                {value && value.map((item, i) => {
                    return (
                        <Flex justify='space-between' style={{ marginTop: 1 }} key={i}>
                            <Flex style={{margin: '0 1px'}}>
                                <Select
                                    style={{width: '40px'}}
                                    value={item[0]}
                                    onChange={(value) => onTypeChange(i, value)}
                                    options={options}
                                />
                                <Input style={{width: '40px'}} placeholder="key" onChange={(value) => onKeyChange(i, value)} value={item[1]} />
                            </Flex>
                            {
                                selectedInputs[i]
                            }
                            <Button tabIndex={-1} style={{ marginLeft: 1 }} size="small" icon={<MinusOutlined />} onClick={() => onRemoveItem(i)} />
                        </Flex>
                    )
                })}
                <Flex justify='end'>
                    <Button style={{marginTop: 1}} size={"small"} icon={<PlusOutlined />} onClick={onAddItem} />
                </Flex>
            </Flex>
        </Flex>
    );
}

export function SelectionWidget({ name, def, onChange, choices, multiple_allowed }) {
    const options = useMemo(() => {
        if (!choices) {
            return [];
        }
        return choices.map((choice) => {
            return {
                label: choice,
                value: choice,
            };
        });
    }, [choices]);

    return (
        <div className="input-container">
            {name &&
                <Text>{name}</Text>
            }
            <Select onChange={onChange} options={options} value={def} multipleAllowed={multiple_allowed} />
        </div>
    );
}

type SelectProps = {
    onChange: (value: string | string[]) => void,
    options: { label: string, value: string }[],
    value: any,
    style?: React.CSSProperties,
    multipleAllowed?: boolean,
};

function Select({ onChange, options, value, style, multipleAllowed }: SelectProps) {
    const [open, setOpen] = useState(false);

    const onSelect = useCallback((val) => {
        if (multipleAllowed) {
            onChange([...value, val]);
        } else {
            onChange(val);
        }
        setOpen(false);
        console.log(val);
    }, [setOpen, open, multipleAllowed, value]);

    const onDeselect = useCallback((val) => {
        if (multipleAllowed) {
            onChange(value.filter((v) => v !== val));
        }
    }, [value]);

    const onClick = useCallback(() => {
        setOpen(!open);
    }, [setOpen, open]);

    return (
        <ASelect
            mode={multipleAllowed ? 'multiple' : undefined}
            style={style}
            options={options}
            value={value}
            onClick={onClick}
            open={open}
            onSelect={onSelect}
            onDeselect={onDeselect}
            dropdownStyle={{minWidth: '90px'}}
        />
    );
}

type InputNumberProps = {
    onChange: (value: number) => void,
    label?: string,
    value?: number,
    placeholder?: string,
};

function InputNumber({ onChange, label, value, placeholder }: InputNumberProps) {
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
                placeholder={placeholder}
            />
        </div>
    );
}

type InputProps = {
    onChange: (value: string) => void,
    label?: string,
    value?: string,
    placeholder?: string,
    style?: React.CSSProperties,
};

function Input({ onChange, label, value, placeholder, style }: InputProps) {
    const { token } = useToken();
    const defaultFocusedStyle = { border: `1px solid ${token.colorBorder}` };
    const [focusedStyle, setFocusedStyle] = useState(defaultFocusedStyle)

    const inputStyle = {
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
        ...style,
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
                placeholder={placeholder}
            />
        </div>
    );
}

export const isWidgetType = (type) => {
    return ['number', 'string', 'boolean', 'bool', 'function', 'selection'].includes(type) || type.startsWith('list') || type.startsWith('dict');
};
