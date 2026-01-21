
# 闭环描述

## 基础

1. evaluator/ 后端提供了针对 repo 的扫描能力
2. webapp/ 前端提供了扫描功能并支持输入1-N个repo开始扫描并展示扫描结果

## 设计

1. 设计扫描分析引擎的插件机制，满足：
  * 在根目录的 plugins 目录下，每个插件一个子目录，
    * 例如 plugins/zgc_simple
        * 第一个版本的扫描代码重构成这个
    * 例如 plugins/zgc_ai_native_2026
        * 以 engineer_level.md 的需求作为该插件的扫描实现，第一版只要初步实现即可
2. 每个插件目录包结构如下：

```
└── zgc_simple
    ├── index.yaml
    ├── scan
    │   └── __init__.py
    └── view
```

其中 index.yaml 描述了该插件的元数据，方便后端和前端解析后加载
其中 scan 是扫描引擎实现
其中 view 是符合 webapp 下的前端框架动态加载使用的前端插件实现

## 实现

# TODO_LIST



