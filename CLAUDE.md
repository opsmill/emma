# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Emma is an experimental AI-powered assistant for Infrahub, a network infrastructure management platform. It's built as a multi-page Streamlit application that helps users manage infrastructure schemas and data.

## Commands

### Development

```bash
# Install dependencies
poetry install

# Run the application
poetry run streamlit run main.py

# Format code
poetry run invoke format

# Run all linters (yaml, ruff, mypy, pylint)
poetry run invoke lint

# Run tests
pytest

# Run specific test
pytest tests/test_file.py::test_function
```

### Documentation (in docs/ directory)

```bash
cd docs
npm install
npm run start  # Development server
npm run build  # Build documentation

# Markdown linting (run from project root)
markdownlint docs/docs/**/*.mdx
markdownlint --fix docs/docs/**/*.mdx  # Auto-fix issues

# Vale documentation style validation (requires Vale to be installed)
vale $(find ./docs -type f \( -name "*.mdx" -o -name "*.md" \) | grep -v node_modules)
```

### Docker

```bash
docker build .
docker-compose up  # Runs on port 8501
```

## Architecture

### Core Structure

- **main.py**: Entry point - Emma homepage
- **menu.py**: Sidebar navigation system
- **emma/**: Core Python module with utilities and services
    - `infrahub.py`: Infrahub API integration
    - `assistant_utils.py`: AI assistant utilities
    - `streamlit_utils.py`: UI utilities
- **pages/**: Individual Streamlit pages for features
    - Schema management: builder, loader, visualizer
    - Data operations: importer, exporter
    - Schema library browser

### AI Integration

Emma integrates with OpenAI/LangChain for schema generation. The schema builder uses an AI assistant to help users create infrastructure schemas based on natural language descriptions. Key files:

- `pages/schema_builder.py`: Main AI-powered schema builder
- `emma/assistant_utils.py`: AI assistant utilities

### Schema System

Infrastructure schemas are YAML-based and stored in `schema-library/`. They define data models for network infrastructure components. The schema system includes:

- Base schemas (DCIM, IPAM, Location, Organization)
- Extensions (Routing, Security, Compute, etc.)
- Schema visualization and validation

### Key Dependencies

- Streamlit for web UI
- Infrahub SDK for backend operations
- OpenAI/LangChain for AI features
- Poetry for dependency management
- Ruff, MyPy, Pylint for code quality

## Development Guidelines

### Code Style

- Python 3.10-3.12 compatibility required
- Follow existing patterns in `emma/` utilities
- Use type hints where possible
- All code must pass linting checks

### Testing

- Tests use pytest framework
- Test configuration in `pyproject.toml`
- Add tests for new features in appropriate test files

### Schema Development

- Schemas are YAML files in `schema-library/`
- Follow existing schema structure and naming conventions
- Include proper descriptions and examples
- Test schemas with the schema visualizer before committing

### Documentation Guidelines

- All documentation files are in `docs/docs/` and use `.mdx` format
- **ALWAYS run markdownlint before committing documentation changes**: `markdownlint docs/docs/**/*.mdx`
- Use `markdownlint --fix docs/docs/**/*.mdx` to automatically fix formatting issues
- Follow the project's `.markdownlint.yaml` configuration
- Test documentation builds with `cd docs && npm run build` before submitting
- Documentation follows the Diataxis framework (Getting Started, Features, Guides, Reference)

## Prompt for Writing Technical Documentation for Infrahub

This master prompt serves as a comprehensive guide for AI systems tasked with writing technical documentation for Infrahub by OpsMill. The prompt defines the objectives, structure, tone, style, and key considerations necessary to produce clear, useful, and accurate documentation tailored to the needs of Infrahub users.

The documentation structure follows the [Diataxis framework](https://diataxis.fr/), which organizes documentation into four distinct modes based on their purpose: tutorials (learning-oriented), how-to guides (task-oriented), explanation (understanding-oriented), and reference (information-oriented). This prompt focuses primarily on how-to guides and explanation documentation to ensure content meets users' specific needs effectively.

### 🧑‍💻 Role Definition

The assumed role for generating documentation is that of an Expert Technical Writer and MDX Generator.

This role goes beyond traditional writing, it combines:

- Deep understanding of infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Awareness of developer ergonomics

### 🔍 Overview of Infrahub

Infrahub from OpsMill is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run. Infrahub offers a central hub to manage the data, templates and playbooks that powers your infrastructure by combining the version control and branch management capabilities similar to Git with the flexible data model and UI of a graph database.

Documentation generated for Infrahub must reflect this novel approach, providing clarity around new concepts and demonstrating how they integrate with familiar patterns from existing tools like Git, infrastructure-as-code, and CI/CD pipelines.

### 🎯 Purpose of Documentation

The documentation must:

- Guide users through installing, configuring, and using Infrahub in real-world workflows.
- Explain concepts and system architecture clearly, including new paradigms introduced by Infrahub.
- Support troubleshooting and advanced use cases with actionable, well-organized content.
- Enable adoption by offering approachable examples and hands-on guides that lower the learning curve.

The documentation is both an onboarding and a reference tool, serving developers, DevOps engineers, and platform teams.

### 🖋️ Tone and Style

- Professional but approachable: Avoid jargon unless well defined. Use plain language with technical precision.
- Concise and direct: Prefer short, active sentences. Reduce fluff.
- Informative over promotional: Focus on explaining how and why, not on marketing.
- Consistent and structured: Follow a predictable pattern across sections and documents.

#### For Guides

- Use conditional imperatives: "If you want X, do Y. To achieve W, do Z."
- Focus on practical tasks and problems, not the tools themselves
- Address the user directly using imperative verbs: "Configure...", "Create...", "Deploy..."
- Maintain focus on the specific goal without digressing into explanations
- Use clear titles that state exactly what the guide shows how to accomplish

#### For Topics

- Use a more discursive, reflective tone that invites understanding
- Include context, background, and rationale behind design decisions
- Make connections between concepts and to users' existing knowledge
- Present alternative perspectives and approaches where appropriate
- Use illustrative analogies and examples to deepen understanding

### 📄 Source and Style References

The project uses the following style configuration:

- [.markdownlint.yaml](.markdownlint.yaml) - Contains Markdown linting rules to ensure consistency in formatting

### 🧰 Terminology and Naming Conventions

- Always define new terms when first used. Use callouts or glossary links if possible.
- Prefer domain-relevant language that reflects the user's perspective (e.g., playbooks, branches, schemas, commits).
- Be consistent: follow naming conventions established by Infrahub's data model and UI.

### 👤 Audience Considerations

- Primary audience: Automation engineers, Software engineers, Network operation teams, infrastructure teams.
- Assumed knowledge: Basic understanding of Git, CI/CD, YAML/JSON, and infrastructure-as-code tools.
- Not assumed: Prior knowledge of Infrahub. All core concepts must be introduced from first principles.

Adjust complexity and terminology accordingly, erring on the side of accessibility.

### 🪵 Document Structure and Patterns Following Diataxis

#### Guides Structure (Task-oriented, practical steps)

How-to guides help users solve real-world problems and achieve specific goals with Infrahub. They are goal-oriented, focused on tasks, and follow a logical sequence of actions.

```markdown
- Title and Metadata
    - Title should clearly state what problem is being solved (YAML frontmatter)
    - Begin with "How to..." to signal the guide's purpose
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief statement of the specific problem or goal this guide addresses
    - Context or real-world use case that frames the guide
    - Clearly indicate what the user will achieve by following this guide
    - Optional: Links to related topics or more detailed documentation
- Prerequisites / Assumptions
    - What the user should have or know before starting
    - Environment setup or requirements
    - What prior knowledge is assumed
- Step-by-Step Instructions
    - Step 1: [Action/Goal]
        - Clear, actionable instructions focused on the task
        - Code snippets (YAML, GraphQL, shell commands, etc.)
        - Screenshots or images for visual guidance
        - Tabs for alternative methods (e.g., Web UI, GraphQL, Shell/cURL)
        - Notes, tips, or warnings as callouts
    - Step 2: [Action/Goal]
        - Repeat structure as above for each step
    - Step N: [Action/Goal]
        - Continue as needed
- Validation / Verification
    - How to check that the solution worked as expected
    - Example outputs or screenshots
    - Potential failure points and how to address them
- Advanced Usage / Variations
    - Optional: Alternative approaches for different circumstances
    - Optional: How to adapt the solution for related problems
    - Optional: Ways to extend or optimize the solution
- Related Resources
    - Links to related guides, reference materials, or explanation topics
    - Optional: Embedded videos or labs for further learning
```

#### Topics Structure (Understanding-oriented, theoretical knowledge)

Topic or explanation documentation helps users understand concepts, background, and context. It's understanding-oriented and provides theoretical knowledge that serves the user's study of Infrahub.

```markdown
- Title and Metadata
    - Title should clearly indicate the topic being explained (YAML frontmatter)
    - Consider using "About..." or "Understanding..." in the title
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief overview of what this explanation covers
    - Why this topic matters in the context of Infrahub
    - Questions this explanation will answer
- Main Content Sections
    - Concepts & Definitions
        - Clear explanations of key terms and concepts
        - How these concepts fit into the broader system
    - Background & Context
        - Historical context or evolution of the concept/feature
        - Design decisions and rationale behind implementations
        - Technical constraints or considerations
    - Architecture & Design (if applicable)
        - Diagrams, images, or explanations of structure
        - How components interact or relate to each other
    - Mental Models
        - Analogies and comparisons to help understanding
        - Different ways to think about the topic
    - Connection to Other Concepts
        - How this topic relates to other parts of Infrahub
        - Integration points and relationships
    - Alternative Approaches
        - Different perspectives or methodologies
        - Pros and cons of different approaches
- Further Reading
    - Links to related topics, guides, or reference materials
    - External resources for deeper understanding
```

### ✅ Quality and Clarity Checklist

Before submitting documentation, validate:

- Content is accurate and reflects the latest version of Infrahub
- Instructions are clear, with step-by-step guidance where needed
- Markdown formatting is correct and compliant with Infrahub's style
- Spelling and grammar are checked

#### For Guides

- The guide addresses a specific, practical problem or task
- The title clearly indicates what will be accomplished
- Steps follow a logical sequence that maintains flow
- Each step focuses on actions, not explanations
- The guide omits unnecessary details that don't serve the goal
- Validation steps help users confirm their success
- The guide addresses real-world complexity rather than oversimplified scenarios

#### For Topics

- The explanation is bounded to a specific topic area
- Content provides genuine understanding, not just facts
- Background and context are included to deepen understanding
- Connections are made to related concepts and the bigger picture
- Different perspectives or approaches are acknowledged where relevant
- The content remains focused on explanation without drifting into tutorial or reference material
- The explanation answers "why" questions, not just "what" or "how"
