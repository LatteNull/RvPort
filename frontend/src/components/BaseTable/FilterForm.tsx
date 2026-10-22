import type { QueryKey } from '@tanstack/react-query'
import type { InputProps, SelectProps } from 'antd'
import { Flex, Form, Input, Select } from 'antd'

import DebouncedSearchInput from '@/components/DebouncedSearchInput'

import type { BaseTableFilterField, BaseTableFilters } from './types'

import styles from './index.module.scss'

interface FilterFormProps<TFilters extends object> {
  queryKey: QueryKey
  searchResetVersion: number
  filters: BaseTableFilters<TFilters>
  values: TFilters
  onFieldChange: (name: Extract<keyof TFilters, string>, value: unknown) => void
}

function FilterField<TFilters extends object>({
  field,
  queryKey,
  searchResetVersion,
  values,
  onFieldChange
}: {
  field: BaseTableFilterField<TFilters>
  queryKey: QueryKey
  searchResetVersion: number
  values: TFilters
  onFieldChange: (name: Extract<keyof TFilters, string>, value: unknown) => void
}) {
  const value = values[field.name]
  const controlId = `filter-${field.key ?? field.name}`
  const ariaLabel = field.ariaLabel ?? field.placeholder ?? field.name
  const updateValue = (nextValue: unknown) => {
    onFieldChange(field.name, field.normalize ? field.normalize(nextValue) : nextValue)
  }

  if (field.type === 'custom') {
    return field.render?.({
      filters: values,
      onChange: updateValue,
      value
    })
  }

  if (field.type === 'select') {
    return (
      <Select
        allowClear
        aria-label={ariaLabel}
        id={controlId}
        options={field.options}
        placeholder={field.placeholder}
        value={value}
        onChange={updateValue}
        {...(field.controlProps as SelectProps)}
      />
    )
  }

  if (field.type === 'search') {
    return (
      <DebouncedSearchInput
        {...(field.controlProps as InputProps)}
        aria-label={ariaLabel}
        autoComplete="off"
        draftStateKey={['base-table-search-draft', ...queryKey, field.name]}
        resetKey={searchResetVersion}
        id={controlId}
        name={field.name}
        placeholder={field.placeholder}
        value={(value as string | undefined) ?? ''}
        onSearch={updateValue}
      />
    )
  }

  return (
    <Input
      allowClear
      aria-label={ariaLabel}
      autoComplete="off"
      id={controlId}
      name={field.name}
      placeholder={field.placeholder}
      value={(value as string | undefined) ?? ''}
      onChange={(event) => updateValue(event.target.value)}
      {...(field.controlProps as InputProps)}
    />
  )
}

export default function FilterForm<TFilters extends object>({
  filters,
  queryKey,
  searchResetVersion,
  values,
  onFieldChange
}: FilterFormProps<TFilters>) {
  return (
    <Form component={false}>
      <Flex wrap className={styles.filterFields} gap={8}>
        {filters.fields.map((field) => (
          <div className={styles.filterField} key={field.key ?? field.name}>
            <FilterField
              field={field}
              queryKey={queryKey}
              searchResetVersion={searchResetVersion}
              values={values}
              onFieldChange={onFieldChange}
            />
          </div>
        ))}
      </Flex>
    </Form>
  )
}
